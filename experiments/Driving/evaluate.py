"""A script for evaluating trained RL policies."""
import argparse

import ray

from ray.tune.registry import register_env

import baposgmcp.rllib as ba_rllib

from ray.rllib.agents.ppo import PPOTrainer

from exp_utils import registered_env_creator, get_rllib_env


def _trainer_make_fn(config):
    return PPOTrainer(env=config["env_config"]["env_name"], config=config)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "env_name", type=str,
        help="Name of the environment to train on."
    )
    parser.add_argument(
        "policy_dir", type=str,
        help="Path to dir containing trained RL policies"
    )
    parser.add_argument(
        "--num_episodes", type=int, default=100,
        help="Number of evaluation episodes to run."
    )
    parser.add_argument(
        "--render", action="store_true",
        help="Render environment."
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Random seed."
    )
    args = parser.parse_args()

    # check env name is valid
    sample_env = get_rllib_env(args)

    ray.init()
    register_env(args.env_name, registered_env_creator)

    eval_config = {
        "env_config": {
            "env_name": args.env_name,
            "seed": args.seed
        },
        "render_env": args.render,
        # If True, store videos in this relative directory inside the default
        # output dir (~/ray_results/...)
        # Must be True for rendering to work, not sure why :/
        "record_env": args.render,
        "evaluation_interval": 1,
        # In episodes (by default)
        # Can be changed to 'timesteps' if desired
        "evaluation_duration": args.num_episodes,
        "evaluation_duration_unit": "episodes",
    }

    print("\n== Importing Graph ==")
    igraph, trainer_map = ba_rllib.import_igraph_trainers(
        igraph_dir=args.policy_dir,
        env_is_symmetric=True,
        trainer_make_fn=_trainer_make_fn,
        trainers_remote=False,
        policy_mapping_fn=None,
        extra_config=eval_config,
        seed=args.seed
    )
    igraph.display()

    ba_rllib.run_evaluation(trainer_map, verbose=True)