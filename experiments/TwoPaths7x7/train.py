"""A script training RL policies."""
import argparse
from itertools import product

import ray

from ray.tune.registry import register_env

from ray.rllib.policy.policy import PolicySpec
from ray.rllib.agents.ppo import PPOTrainer, PPOTorchPolicy
from ray.rllib.examples.policy.random_policy import RandomPolicy

from baposgmcp import pbt
import baposgmcp.rllib as ba_rllib

from exp_utils import (
    ENV_CONFIG, env_creator, EXP_RL_POLICY_DIR,
    ENV_NAME, get_br_policy_mapping_fn
)


# NUM_GPUS = int(os.environ.get("RLLIB_NUM_GPUS", "0"))
NUM_GPUS = 1

# Ref: https://docs.ray.io/en/latest/rllib/rllib-training.html#configuration
RL_TRAINER_CONFIG = {
    "env_config": ENV_CONFIG,
    # == Rollout worker processes ==
    # A single rollout worker
    "num_workers": 1,
    "num_envs_per_worker": 1,
    # == Trainer process and PPO Config ==
    # ref: https://docs.ray.io/en/latest/rllib/rllib-algorithms.html#ppo
    "gamma": 0.95,
    "use_critic": True,
    "use_gae": True,
    "lambda": 1.0,
    "kl_coeff": 0.2,
    "rollout_fragment_length": 100,   # = episode length for TwoPaths7x7
    "train_batch_size": 2048,
    # "train_batch_size": 256,
    "sgd_minibatch_size": 256,
    "shuffle_sequences": True,
    "num_sgd_iter": 6,
    # "num_sgd_iter": 1,
    "lr": 0.0003,
    "lr_schedule": None,
    "vf_loss_coeff": 0.05,
    "model": {
        "use_lstm": True,
        "vf_share_layers": True,
    },
    "entropy_coeff": 0.0,
    "entropy_coeff_schedule": None,
    "clip_param": 0.3,
    "vf_clip_param": 15.0,
    "grad_clip": None,
    "kl_target": 0.01,
    # "trancate_episodes" or "complete_episodes"
    "batch_mode": "truncate_episodes",
    "optimizer": {},
    # == Environment settings ==
    # ...

    # == Deep LEarning Framework Settings ==
    "framework": "torch",
    # == Exploration Settings ==
    "explore": True,
    "exploration_config": {
        "type": "StochasticSampling"
    },
    # == Evaluation settings ==
    "evaluation_interval": None,
    "evaluation_duration": 10,
    "evaluation_duration_unit": "episodes",
    # == Advanced Rollout Settings ==
    "observation_filter": "NoFilter",
    "metrics_num_episodes_for_smoothing": 100,
    # == Resource Settungs ==
    # we set this to 1.0 and control resource allocation via ray.remote
    # num_gpus controls the GPU allocation for the learner process
    # we want the learner using the GPU as it does batch inference
    "num_gpus": 1.0,
    "num_cpus_per_worker": 0.5,
    # number of gpus per rollout worker.
    # this should be 0 since we want rollout workers using CPU since they
    # don't do batch inference
    "num_gpus_per_worker": 0.0
}


def _get_trainers_and_igraph(args):
    sample_env = env_creator(ENV_CONFIG)
    # obs and action spaces are the same for both agent in TwoPaths env
    obs_space = sample_env.observation_space["0"]
    act_space = sample_env.action_space["0"]

    l0_policy_spec = PolicySpec(RandomPolicy, obs_space, act_space, {})
    k_policy_spec = PolicySpec(PPOTorchPolicy, obs_space, act_space, {})

    agent_ids = list(sample_env.get_agent_ids())
    agent_ids.sort()
    igraph = pbt.construct_klr_interaction_graph(
        agent_ids, args.k, is_symmetric=False
    )

    num_trainers = (args.k+1) * len(agent_ids)
    if args.train_best_response:
        num_trainers += 2

    avail_gpu = args.gpu_utilization * NUM_GPUS
    num_gpus_per_trainer = avail_gpu / num_trainers
    print(f"{num_gpus_per_trainer=}")
    print(f"num_trainers={num_trainers}")

    default_trainer_config = dict(RL_TRAINER_CONFIG)
    default_trainer_config["log_level"] = args.log_level
    default_trainer_config["seed"] = args.seed
    default_trainer_config["env_config"] = {"env_name": ENV_NAME}

    trainers = {i: {} for i in agent_ids}   # type: ignore
    for agent_k_id, k, agent_km1_id in product(
            agent_ids, range(0, args.k+1), agent_ids
    ):
        if agent_k_id == agent_km1_id:
            continue

        policy_km1_id = pbt.get_klr_policy_id(agent_km1_id, k-1, False)
        policy_k_id = pbt.get_klr_policy_id(agent_k_id, k, False)
        policies_k = {    # type: ignore
            policy_km1_id: l0_policy_spec if k == 0 else k_policy_spec,
            policy_k_id: k_policy_spec
        }

        trainer_k = ba_rllib.get_remote_trainer(
            ENV_NAME,
            trainer_class=PPOTrainer,
            policies=policies_k,
            policy_mapping_fn=ba_rllib.default_asymmetric_policy_mapping_fn,
            policies_to_train=[policy_k_id],
            num_workers=args.num_workers,
            num_gpus_per_trainer=num_gpus_per_trainer,
            default_trainer_config=default_trainer_config
        )

        trainers[agent_k_id][policy_k_id] = trainer_k
        igraph.update_policy(
            agent_k_id,
            policy_k_id,
            trainer_k.get_weights.remote(policy_k_id)
        )

    if not args.train_best_response:
        return trainers, igraph

    for agent_br_id, agent_k_id in product(agent_ids, agent_ids):
        if agent_br_id == agent_k_id:
            continue

        policy_br_id = pbt.get_br_policy_id(agent_br_id, False)

        policies_br = {policy_br_id: k_policy_spec}
        policies_k_dist = []
        policies_k_ids = []
        for k in range(-1, args.k+1):
            policy_k_id = pbt.get_klr_policy_id(agent_k_id, k, False)
            if k < 0:
                policies_br[policy_k_id] = l0_policy_spec
            else:
                policies_br[policy_k_id] = k_policy_spec
            policies_k_dist.append(pbt.get_klr_poisson_prob(
                k, args.k+2, lmbda=1.0
            ))
            policies_k_ids.append(policy_k_id)

        unnormalized_prob_sum = sum(policies_k_dist)
        for i in range(len(policies_k_dist)):
            policies_k_dist[i] /= unnormalized_prob_sum

        br_policy_mapping_fn = get_br_policy_mapping_fn(
            policy_br_id, agent_br_id, policies_k_ids, policies_k_dist
        )

        trainer_br = ba_rllib.get_remote_trainer(
            ENV_NAME,
            trainer_class=PPOTrainer,
            policies=policies_br,
            policy_mapping_fn=br_policy_mapping_fn,
            policies_to_train=[policy_br_id],
            num_workers=args.num_workers,
            num_gpus_per_trainer=num_gpus_per_trainer,
            default_trainer_config=default_trainer_config
        )

        trainers[agent_br_id][policy_br_id] = trainer_br
        igraph.add_policy(
            agent_br_id,
            policy_br_id,
            trainer_br.get_weights.remote(policy_br_id)
        )
        for policy_id, policy_prob in zip(policies_k_ids, policies_k_dist):
            igraph.add_edge(
                agent_br_id, policy_br_id, agent_k_id, policy_id, policy_prob
            )

    return trainers, igraph


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "-k", "--k", type=int, default=3,
        help="Number of reasoning levels"
    )
    parser.add_argument(
        "--num_iterations", type=int, default=50,
        help="Number of iterations to train."
    )
    parser.add_argument(
        "--num_workers", type=int, default=1,
        help="Number of worker processes per trainer"
    )
    parser.add_argument(
        "--log_level", type=str, default='WARN',
        help="Log level"
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Random seed."
    )
    parser.add_argument(
        "-gpu", "--gpu_utilization", type=float, default=0.9,
        help="Proportion of availabel GPU to use."
    )
    parser.add_argument(
        "-br", "--train_best_response", action="store_true",
        help="Train a best response on top of KLR policies."
    )
    parser.add_argument(
        "--save_policies", action="store_true",
        help="Save policies to file."
    )

    args = parser.parse_args()

    ray.init()
    register_env(ENV_NAME, env_creator)

    trainers, igraph = _get_trainers_and_igraph(args)
    igraph.display()

    ba_rllib.run_training(trainers, igraph, args.num_iterations, verbose=True)

    if args.save_policies:
        print("== Exporting Graph ==")
        export_dir = ba_rllib.export_trainers_to_file(
            EXP_RL_POLICY_DIR, igraph, trainers, ENV_NAME
        )
        print(f"{export_dir=}")