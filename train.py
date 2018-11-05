# import gym
import yaml
import numpy as np
import tensorflow as tf
from tensorflow.summary import FileWriter

from ddpg import DDPG
# from reward import Reward
from environment import G2Goal


def load_config(filename):
    with open(filename) as f:
        config = yaml.load(f.read())
    return config


def scale_action(u):
    return (u+1)/2. * [0.2, np.pi/2] + [0, -np.pi/4]


def train(config):
    # reward_normalizer = Reward(0.1, config["gamma"])
    # env = gym.make(config["env_name"])
    env = G2Goal()
    # env.seed(134)
    # visual = Visualizer(env.env, 4, 1, [-5, 5, -5, 5])
    # visual.thread.start()
    is_u_discrete = len(env.action_space.shape) == 0
    tf_session = tf.Session()
    ddpg_agent = DDPG(tf_session, config)
    tf_session.run(tf.global_variables_initializer())

    # print(ddpg_agent.actor.pi.net_params)
    # exit()
    saver = tf.train.Saver()
    summarizer = FileWriter("__tensorboard/her2", tf_session.graph)
    s_summary = tf.Summary()
    log_str = "| [{}] Episode: {:4} | Reward: {:7d} | Q: {:8.3f} | T: {:3d} | MIND: {:4.3f} |"
    # log_str_e = "| [{}] EvalRun: {:4} | Reward: {:4.2f} | Q: {:8.3f} |"
    summary_op = tf.summary.merge_all()

    # for testing purposes!!!
    current_best_eval_score = 0
    for episode in range(config["n_episodes"]):
        episodic_r = 0.
        episodic_q = 0.
        obs = env.reset()
        episode_batch = []
        min_d2goal = env.get_current_distance()
        for i in range(env._max_episode_steps):
            # print(obs)
            action, u, q = ddpg_agent.step(np.hstack([obs["obs"],
                                           obs["goal"]]),
                                           is_u_discrete)
            episodic_q += q
            # print("ACTION BEFORE: ", action)
            action = scale_action(action)
            # print("ACTION AFTER : ", action)
            # print(env.env.agents[0].pose)
            new_obs, r, done, info = env.step(action)
            # print(action)
            # print(env.env.agents[0].pose)
            # print(new_obs, r, done)
            ogag = [obs[k] for k in ["obs", "goal", "ag"]]
            episode_batch.append([*ogag, u, r, new_obs["obs"],
                                  new_obs["goal"], int(done)])
            if info["dist"] < min_d2goal:
                min_d2goal = info["dist"]
            # print([*ogag, u, r, new_obs["obs"], int(done)])
            # if episode == 2:
            #     exit()
            obs = new_obs
            if "render" in config.keys() and config["render"]:
                env.render()
            episodic_r += r
            for epoch in range(5):
                ddpg_agent.train()
            if done:
                break
            s_summary.value.add(tag="run/l_velocity", simple_value=(action)[0])
            s_summary.value.add(tag="run/a_velocity", simple_value=(action)[1])
            s_summary.value.add(tag="run/meanQ",
                                simple_value=float(episodic_q/(i+1)))
            summarizer.add_summary(s_summary, episode*env._max_episode_steps+i)
        # n_batch = reward_normalizer.discount(episode_batch)
        for experience in episode_batch:
            ddpg_agent.remember(experience)
        print(log_str.format("T", episode+1, int(episodic_r),
                             float(episodic_q), i+1, min_d2goal))
        summarizer.add_summary(tf_session.run(summary_op), episode)
        summarizer.flush()
        # To run or not to run evaluations on current target policy...
        if (episode+1) % 20 != 0:
            continue
        m_eval_score = 0.
        m_eval_q = 0.
        print()
        for eval_run in range(5):
            eval_score = 0.
            eval_q = 0.
            obs = env.reset()
            for j in range(env._max_episode_steps):
                u, _, q = ddpg_agent.step(np.hstack([obs["obs"], obs["goal"]]),
                                          is_u_discrete, explore=False)
                obs, r, done, _ = env.step(u)
                eval_score += r
                eval_q += q
                if done:
                    break
            m_eval_q += eval_q
            m_eval_score += eval_score
            print(log_str.format("E", eval_run+1, int(eval_score),
                                 float(m_eval_q), j+1, -1))
        print()
        # save the model checkpoints if they are the current best...
        if m_eval_score > current_best_eval_score:
            print("New best policy found with eval score of: ", m_eval_score)
            print("old best policy's eval score: ", current_best_eval_score)
            current_best_eval_score = m_eval_score
            saver.save(tf_session, "__checkpoints/nb_policy", episode)


def exit():
    import sys
    sys.exit(0)


def main():
    config = load_config("config_g2g.yaml")
    print()
    print(train(config))


if __name__ == "__main__":
    main()
