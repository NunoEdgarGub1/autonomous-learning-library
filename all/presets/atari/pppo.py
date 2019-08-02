# /Users/cpnota/repos/autonomous-learning-library/all/approximation/value/action/torch.py
import torch
from torch.optim import Adam
from torch.optim.lr_scheduler import LambdaLR
from all.agents.pppo import PPPO
from all.bodies import ParallelAtariBody
from all.approximation import VNetwork, FeatureNetwork, PolyakTarget
from all.logging import DummyWriter
from all.policies import SoftmaxPolicy
from .models import nature_cnn, nature_value_head, nature_policy_head


def pppo(
        # stable baselines hyperparameters
        clip_grad=0.5,
        discount_factor=0.99,
        lam=0.95,  # GAE lambda (similar to e-traces)
        lr_pi=2.5e-4,  # Adam learning rate
        lr_v=2.5e-4,
        eps=1e-5,  # Adam stability
        entropy_loss_scaling=0.03,
        value_loss_scaling=0.5,
        epochs=4,
        minibatches=4,
        n_envs=8,
        n_steps=128,
        polyak=0.001,
        lr_half_life=10e6,
        device=torch.device("cpu"),
):
    # Update epoch * minibatches times per update,
    # but we only update once per n_steps,
    # with n_envs and 4 frames per step
    half_life = lr_half_life * epochs * minibatches / (n_steps * n_envs * 4)
    lr_lambda = lambda epoch: half_life / (half_life + epoch)

    def _pppo(envs, writer=DummyWriter()):
        env = envs[0]

        value_model = nature_value_head().to(device)
        policy_model = nature_policy_head(envs[0]).to(device)
        feature_model = nature_cnn().to(device)

        feature_optimizer = Adam(
            feature_model.parameters(), lr=lr_pi, eps=eps
        )
        value_optimizer = Adam(value_model.parameters(), lr=lr_v, eps=eps)
        policy_optimizer = Adam(policy_model.parameters(), lr=lr_pi, eps=eps)

        features = FeatureNetwork(
            feature_model,
            feature_optimizer,
            clip_grad=clip_grad,
            scheduler=LambdaLR(
                feature_optimizer,
                lr_lambda
            ),
            writer=writer,
            target=PolyakTarget(polyak),
        )
        v = VNetwork(
            value_model,
            value_optimizer,
            loss_scaling=value_loss_scaling,
            clip_grad=clip_grad,
            writer=writer,
            scheduler=LambdaLR(
                value_optimizer,
                lr_lambda
            ),
            target=PolyakTarget(polyak),
        )
        policy = SoftmaxPolicy(
            policy_model,
            policy_optimizer,
            env.action_space.n,
            entropy_loss_scaling=entropy_loss_scaling,
            clip_grad=clip_grad,
            writer=writer,
            scheduler=LambdaLR(
                policy_optimizer,
                lr_lambda
            ),
            target=PolyakTarget(polyak),
        )

        return ParallelAtariBody(
            PPPO(
                features,
                v,
                policy,
                epochs=epochs,
                minibatches=minibatches,
                n_envs=n_envs,
                n_steps=n_steps,
                discount_factor=discount_factor,
                lam=lam,
            ),
            envs,
        )

    return _pppo, n_envs


__all__ = ["pppo"]