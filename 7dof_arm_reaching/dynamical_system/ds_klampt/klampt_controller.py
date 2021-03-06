

import time, traceback
from copy import deepcopy as copy
from tqdm import tqdm, trange
import numpy as np

from klampt import WorldModel
from klampt.model.collide import WorldCollider
from klampt.model import ik
from modulation import Modulator

from pybulletgym.envs.roboschool.envs.manipulation.panda_reacher_env import PandaReacherEnv

import sys
epsilon = sys.float_info.epsilon
from matplotlib import pyplot

class PandaReacherEarlyTerminateEnv(PandaReacherEnv):
	'''
	a modified environment that runs for a maximum of 500 time steps, but terminates when the target is reached. 
	'''
	def __init__(self, shelf=True, timelimit=500, target_threshold=0.03, mode = 'human'):
		super(PandaReacherEarlyTerminateEnv, self).__init__(shelf=shelf)
		self.timelimit = timelimit
		self.target_threshold = target_threshold
		self.rgb_array  = np.array([])

	def reset(self, **kwargs):
		self.cur_time = 0
		super().reset(**kwargs)

	def step(self, a):
		s, r, done, info = super().step(a)
		self.cur_time += 1
		# print(self.cur_time)
		done = done or self.cur_time == self.timelimit or np.linalg.norm(s[19:22]) <= self.target_threshold
		return s, r, done, info

	def render(self, mode='human', **kwargs):
		super().render(mode=mode,  **kwargs)

	def s(self):
		return self.robot.calc_state()

	def log_prior(self, target_loc):
		assert -0.5 <= target_loc[0] <= -0.05 or 0.05 <= target_loc[0] <= 0.5
		assert -0.3 <= target_loc[1] <= 0.2 and 0.65 <= target_loc[2] <= 1
		return 0

class DSController():
	def __init__(self):
		self.world = WorldModel()
		self.robot = self.world.loadRobot('franka_panda/panda_model_w_table.urdf')
		self.robot.setJointLimits(
			[-0.0, -0.0, -0.0, -0.0, -0.0, -0.0, -0.0, -2.9671, -1.8326, -2.9671, -3.1416, -2.9671, -0.0873, -2.9671, 0.0, 0.0, 0.0], 
			[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 2.9671, 1.8326, 2.9671, 0.0, 2.9671, 3.8223, 2.9671, 0.0, 0.0, 0.0]
		)
		self.grasptarget_link = self.robot.link(16)
		self.model_filename   = "../dynamical_system_modulation_svm/models/gammaSVM_frankaROCUS_bounded_pyb.pkl"
		reference_points  = np.array([[0, 0.15, 0.975], [0.0, 0.5, 0.80], [0.0, 0, 0.61]])
		self.modulator        = Modulator(self.model_filename, reference_points)
		# time.sleep(1)

	def ik(self, from_config, to_ee_loc, return_flag=False):
		if isinstance(to_ee_loc, np.ndarray):
			to_ee_loc = list(to_ee_loc.flat)
		from_config_full = copy(self.robot.getConfig())
		from_config_full[7:14] = from_config
		self.robot.setConfig(from_config_full)
		objective = ik.objective(self.grasptarget_link, local=[0, 0, 0], world=to_ee_loc)
		flag = ik.solve(objective, iters=1000, tol=1e-4)
		cfg = self.robot.getConfig()[7:14]
		if not return_flag:
			return cfg
		else:
			return cfg, flag

	def get_trajectory(self, env, kernel=None):
		try:
			s = env.s()
			traj = [s[:10]]
			done = False
			dt   = 0.05 # fake dt
			while not done:
				ee_loc = s[7:10]
				target_loc = s[16:19]
				x_dot = self.modulator.get_modulated_direction(ee_loc, target_loc)
				x_dot = x_dot/np.linalg.norm(x_dot + epsilon) * 0.10
				next_ee_loc     = ee_loc + x_dot * dt
				cur_config = s[:7]
				next_config = self.ik(cur_config, next_ee_loc)
				cfg_diff = np.array(next_config) - cur_config
				cfg_diff = cfg_diff / max(cfg_diff.max(), 0.05)
				s, _, done, _ = env.step(cfg_diff)
				traj.append(s[:10])
				# time.sleep(0.01)
			traj = np.array(traj)
			return traj
		except:
			traceback.print_exc()
			return None

	def log_prior(self, kernel):
		return 0

def visualize_ds(record = False):
	env = PandaReacherEarlyTerminateEnv()
	ds_controller = DSController()	
	for _ in trange(100):
		env.reset()
		traj = ds_controller.get_trajectory(env)


if __name__ == '__main__':
	
	visualize_ds()

