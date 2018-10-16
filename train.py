import torch
import torch.nn.functional as F
from torch.optim import Adam
from torch.optim.lr_scheduler import MultiStepLR
import os
import time

from networks.networks import PointCloudDetector as HawkEye
from datautils.dataloader import *
import config as cnf
from lossUtils import computeLoss
import misc
# from string import Template

torch.manual_seed(0)

# data loaders
train_loader, vali_loader, test_loader = \
	lidarDatasetLoader(cnf.rootDir, cnf.batchSize, cnf.gridConfig, cnf.objtype)

# create detector object and intialize weights
hawkEye = HawkEye(cnf.res_block_layers, cnf.up_sample_layers).to(cnf.device)
hawkEye.apply(misc.weights_init)

# network optimization method
optimizer = Adam(hawkEye.parameters(), lr=cnf.learningRate)
scheduler = MultiStepLR(optimizer, milestones=[20,30], gamma=0.1)

def train(epoch):
	hawkEye.train()

	for batchId, batch_data in enumerate(train_loader):
		data, target, filenames, zoom0_3, zoom1_2 = batch_data
		# move data to GPU
		data = data.to(cnf.device)
		target = target.to(cnf.device)
		zoom1_2 = zoom1_2.to(cnf.device)
		zoom0_3 = zoom0_3.to(cnf.device)

		# empty the gradient buffer
		hawkEye.zero_grad()

		# pass data through network and predict
		cla, loc = hawkEye(data)

		# compute loss, gradient, and optimize
		st = time.time()
		claLoss, locLoss = computeLoss(cla, loc, target, zoom0_3, zoom1_2)
		ed = time.time()
		if claLoss is None:
			trainLoss = None
			ls = cnf.logString3.format(epoch, batchId)
		elif locLoss is not None:
			trainLoss = claLoss + locLoss
			ls = cnf.logString1.format(epoch, batchId, claLoss.item(), locLoss.item(), trainLoss.item())
		else:
			trainLoss = claLoss
			ls = cnf.logString2.format(epoch, batchId, claLoss.item(), trainLoss.item())

		# trainLoss = claLoss+locLoss
		if trainLoss is not None:
			trainLoss.backward()
			optimizer.step()

		# TODO: mAP

		# save the results, loss in a file
		if (epoch+1)==cnf.epochs:
			misc.savebatchOutput(cla, loc, filenames, cnf.trainOutputDir, epoch)
			misc.savebatchTarget(target, filenames, cnf.trainOutputDir, epoch)
		
		misc.writeToFile(cnf.trainlog, ls + 'elapsed time: '+str(ed-st)+' secs\n\n')

def validation(epoch):
	hawkEye.eval()

	for batchId, batch_data in enumerate(vali_loader):
		data, target, filenames, zoom0_3, zoom1_2 = batch_data

		# move data to GPU
		data = data.to(cnf.device)
		target = target.to(cnf.device)
		zoom1_2 = zoom1_2.to(cnf.device)
		zoom0_3 = zoom0_3.to(cnf.device)

		# pass data through network and predict
		cla, loc = hawkEye(data)

		claLoss, locLoss = computeLoss(cla, loc, target, zoom0_3, zoom1_2)
		if claLoss is None:
			valLoss = None
			ls = cnf.logString3.format(epoch, batchId)
		elif locLoss is not None:
			valLoss = claLoss + locLoss
			ls = cnf.logString1.format(epoch, batchId, claLoss.item(), locLoss.item(), valLoss.item())
		else:
			valLoss = claLoss
			ls = cnf.logString2.format(epoch, batchId, claLoss.item(), valLoss.item())


		# TODO mAP

		# save the results, loss in a file
		if (epoch+1)==cnf.epochs:
			misc.savebatchOutput(cla, loc, filenames, cnf.valiOutputDir, epoch)
			misc.savebatchTarget(target, filenames, cnf.valiOutputDir, epoch)
		
		misc.writeToFile(cnf.vallog, ls)

if __name__ == '__main__':
	# current_milli_time = lambda: time.time()*1000
	# start = current_milli_time()

	# load model file if present
	if os.path.isfile(cnf.model_file):
		hawkEye.load_state_dict(torch.load(cnf.model_file,
			map_location=lambda storage, loc: storage))

	for epoch in range(cnf.epochs):
		# learning rate decay scheduler
		scheduler.step()

		st = time.time()
		train(epoch)
		ed = time.time()
		misc.writeToFile(cnf.trainlog, '\n\n\n~~~~~epoch end time taken: '+str(st-ed)+' secs~~~~\n\n\n')

		# run validation every 10 epochs
		if (epoch+1)%10 == 0:
			validation(epoch)

		if (epoch+1)%10 == 0:
			torch.save(hawkEye.state_dict(), cnf.model_file)

	# end = current_milli_time()
	# print('time taken:', (end-start)*1000/60)