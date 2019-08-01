import torch
from all.memory import GeneralizedAdvantageBuffer
from ._agent import Agent


class PPPO(Agent):
    def __init__(
            self,
            features,
            v,
            policy,
            epochs=4,
            minibatches=4,
            n_envs=None,
            n_steps=4,
            discount_factor=0.99,
            lam=0.95
    ):
        if n_envs is None:
            raise RuntimeError("Must specify n_envs.")
        self.features = features
        self.v = v
        self.policy = policy
        self.n_envs = n_envs
        self.n_steps = n_steps
        self.discount_factor = discount_factor
        self.lam = lam
        self._states = None
        self._actions = None
        self._epochs = epochs
        self._batch_size = n_envs * n_steps
        self._minibatches = minibatches
        self._buffer = self._make_buffer()
        self._features = []

    def act(self, states, rewards):
        self._store_transitions(rewards)
        self._train(states)
        self._states = states
        self._actions = self.policy.target(self.features.target(states))
        return self._actions

    def _store_transitions(self, rewards):
        if self._states:
            self._buffer.store(self._states, self._actions, rewards)

    def _train(self, _states):
        if len(self._buffer) >= self._batch_size:
            states, actions, advantages = self._buffer.advantages(_states)
            with torch.no_grad():
                features = self.features.target(states)
                pi_0 = self.policy.target(features, actions)
                targets = self.v.target(features) + advantages
            for _ in range(self._epochs):
                self._train_epoch(states, actions, pi_0, advantages, targets)

    def _train_epoch(self, states, actions, pi_0, advantages, targets):
        minibatch_size = int(self._batch_size / self._minibatches)
        indexes = torch.randperm(self._batch_size)
        for n in range(self._minibatches):
            first = n * minibatch_size
            last = first + minibatch_size
            i = indexes[first:last]
            self._train_minibatch(states[i], actions[i], pi_0[i], advantages[i], targets[i])

    def _train_minibatch(self, states, actions, pi_0, advantages, targets):
        features = self.features(states)
        self.policy(features, actions)
        self.policy.reinforce(self._compute_policy_loss(pi_0, advantages))
        self.v.reinforce(targets - self.v(features))
        self.features.reinforce()

    def _compute_policy_loss(self, pi_0, advantages):
        def _policy_loss(pi_i):
            ratios = torch.exp(pi_i - pi_0)
            return -(ratios * advantages).mean()
        return _policy_loss

    def _make_buffer(self):
        return GeneralizedAdvantageBuffer(
            self.v,
            self.features,
            self.n_steps,
            self.n_envs,
            discount_factor=self.discount_factor,
            lam=self.lam
        )
 