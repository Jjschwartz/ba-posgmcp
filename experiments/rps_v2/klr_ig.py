"""A script for running K-level reasoning training in Rock, Paper, Scissors.

This implementation uses RLlib, and is based on the following examples:
- https://github.com/ray-project/ray/blob/master/rllib/examples/
  rock_paper_scissors_multiagent.py
- https://github.com/ray-project/ray/blob/master/rllib/examples/
  multi_agent_two_trainers.py

Note for each training iteration only a single level is trained at a time.

"""
import os
import sys
import argparse

try:
    from pettingzoo.classic import rps_v2
except ImportError:
    print(
        "This script requires that the PettingZoo library is installed, with "
        "the 'classic' environment dependencies. For installation instructions"
        " visit https://www.pettingzoo.ml/classic."
    )
    sys.exit(1)

import ray

from ray.rllib.env import PettingZooEnv
from ray.rllib.policy.policy import PolicySpec
from ray.rllib.agents.ppo import PPOTrainer, PPOTorchPolicy
from ray.rllib.examples.policy.random_policy import RandomPolicy

from ray.tune.logger import pretty_print
from ray.tune.registry import register_env

from baposgmcp.pbt import InteractionGraph


# pylint: disable=[unused-argument]

parser = argparse.ArgumentParser()
parser.add_argument(
    "--k", type=int, default=1,
    help="Reasoning level (default=1)"
)
parser.add_argument(
    "--stop-iters", type=int, default=150,
    help="Number of iterations to train."
)
parser.add_argument(
    "--stop-timesteps", type=int, default=100000,
    help="Number of timesteps to train."
)


def env_creator(args):
    env = rps_v2.env()
    return env


register_env(
    "RockPaperScissors", lambda config: PettingZooEnv(env_creator(config))
)


if __name__ == "__main__":
    args = parser.parse_args()

    ray.init()

    sample_env = env_creator({})
    obs_space = sample_env.observation_space("player_0")
    act_space = sample_env.action_space("player_0")

    def _policy_mapping_fn(agent_id, episode, worker, **kwargs):
        policy_ids = list(episode.policy_map.keys())
        policy_ids.sort()
        if agent_id == "player_0":
            return policy_ids[0]
        return policy_ids[1]

    base_policy_spec = PolicySpec(RandomPolicy, obs_space, act_space, {})
    lk_policy_spec = PolicySpec(PPOTorchPolicy, obs_space, act_space, {})

    igraph = InteractionGraph()
    igraph.add_policy("pi_-1", {})

    policies = []
    trainers = []
    for k in range(args.k+1):
        policy_lkm1_id = f"pi_{k-1}"
        policy_lk_id = f"pi_{k}"
        policies_lk = {    # type: ignore
            policy_lkm1_id: base_policy_spec if k == 0 else lk_policy_spec,
            policy_lk_id: lk_policy_spec
        }

        trainer_lk = PPOTrainer(
            env="RockPaperScissors",
            config={
                "multiagent": {
                    "policies": policies_lk,
                    "policy_mapping_fn": _policy_mapping_fn,
                    "policies_to_train": [policy_lk_id],
                },
                "model": {
                    "vf_share_layers": True,
                },
                "num_sgd_iter": 6,
                "vf_loss_coeff": 0.01,
                "observation_filter": "MeanStdFilter",
                "num_gpus": int(os.environ.get("RLLIB_NUM_GPUS", "0")),
                "framework": "torch",
            },
        )
        policies.append(policies_lk)
        trainers.append(trainer_lk)

        igraph.add_policy(policy_lk_id, trainer_lk.get_weights(policy_lk_id))
        igraph.add_edge(policy_lk_id, policy_lkm1_id, 1.0)

    for i in range(args.stop_iters):
        print(f"== Iteration {i} ==")

        for k in range(args.k+1):
            print(f"-- Level {k} --")
            policy_lk_id = f"pi_{k}"
            result = trainers[k].train()
            print(pretty_print(result))
            igraph.update_policy(
                policy_lk_id, trainers[k].get_weights(policy_lk_id)
            )

        # swap weights of opponent policies
        for k in range(1, args.k+1):
            policy_lk_id = f"pi_{k}"
            _, opp_weights = igraph.sample_policy(policy_lk_id)
            trainers[k].set_weights(opp_weights)