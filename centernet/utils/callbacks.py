import os
import torch
import scipy.signal
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt
from tensorboardX import SummaryWriter
from torchsummary import summary
import io
from contextlib import redirect_stdout
import threading
import webbrowser
import numpy as np

def launchTensorBoard(tensorBoardPath, port = 8888):
    os.system('tensorboard --logdir=%s --port=%s'%(tensorBoardPath, port))
    url = "http://localhost:%s/"%(port)
    # webbrowser.open_new(url)
    return

class LossHistory():
    def __init__(self, model, patience = 5):
        import datetime
        curr_time = datetime.datetime.now()
        time_str = datetime.datetime.strftime(curr_time,'%Y_%m_%d_%H_%M_%S')
        self.log_dir    = "logs//CenterNet/"
        self.time_str   = time_str
        self.save_path  = os.path.join(self.log_dir, "loss_" + str(self.time_str))
        self.losses     = []
        self.val_loss   = []
        self.writer = SummaryWriter(log_dir=os.path.join(self.log_dir, "run_" + str(self.time_str)))
        self.freeze = False

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        rndm_input = torch.autograd.Variable(torch.rand(1, 3, 512, 512), requires_grad = False).to(device)
        self.writer.add_graph(model, rndm_input)

        f = io.StringIO()
        with redirect_stdout(f):
            summary(model, (3, 512, 512))
        lines = f.getvalue()
        with open(os.path.join(self.log_dir, "summary.txt") ,"w") as f:
            [f.write(line) for line in lines]

        # launch tensorboard
        t = threading.Thread(target=launchTensorBoard, args=([self.log_dir]))
        t.start()     

        # initial EarlyStopping
        self.best_lower_loss = np.Inf 
        self.early_stop = False
        self.counter  = 0
        self.patience = patience
        
        os.makedirs(self.save_path)

    def set_status(self, freeze):
        self.freeze = freeze

    def epoch_loss(self, loss, val_loss, epoch):
        self.losses.append(loss)
        self.val_loss.append(val_loss)
        with open(os.path.join(self.save_path, "epoch_loss_" + str(self.time_str) + ".txt"), 'a') as f:
            f.write(str(loss))
            f.write("\n")
        with open(os.path.join(self.save_path, "epoch_val_loss_" + str(self.time_str) + ".txt"), 'a') as f:
            f.write(str(val_loss))
            f.write("\n")
        
        self.loss_plot()

        prefix = "Freeze_epoch/" if self.freeze else "UnFreeze_epoch/"     
        self.writer.add_scalar(prefix+'Loss/Train', loss, epoch)
        self.writer.add_scalar(prefix+'Loss/Val', val_loss, epoch)
        self.decide(val_loss)

    def step(self, steploss, iteration):        
        prefix = "Freeze_step/" if self.freeze else "UnFreeze_step/"
        self.writer.add_scalar(prefix + 'Train/Loss', steploss, iteration)

    def step_c(self, steploss, iteration):        
        prefix = "Freeze_step/" if self.freeze else "UnFreeze_step/"
        self.writer.add_scalar(prefix + 'Train/Classification_Loss', steploss, iteration)

    def step_r(self, steploss, iteration):        
        prefix = "Freeze_step/" if self.freeze else "UnFreeze_step/"
        self.writer.add_scalar(prefix + 'Train/Regression_Loss', steploss, iteration)

    def decide(self, val_epoch_loss):
        if self.best_lower_loss >= val_epoch_loss:
            self.best_lower_loss = val_epoch_loss
            self.counter = 0
        else:
            self.counter += 1
            print(f'EarlyStopping counter: {self.counter} out of {self.patience}\n')
    
    def earlyStop(self):
        prefix = "Freeze" if self.freeze else "UnFreeze"        
        if(self.counter > self.patience): 
            print(f'EarlyStopping counter: {self.counter} bigger than {self.patience}\n')
            print(f'exit %s training'%(prefix))
        return self.counter > self.patience

    def loss_plot(self):
        iters = range(len(self.losses))

        plt.figure()
        plt.plot(iters, self.losses, 'red', linewidth = 2, label='train loss')
        plt.plot(iters, self.val_loss, 'coral', linewidth = 2, label='val loss')
        try:
            if len(self.losses) < 25:
                num = 5
            else:
                num = 15
            
            plt.plot(iters, scipy.signal.savgol_filter(self.losses, num, 3), 'green', linestyle = '--', linewidth = 2, label='smooth train loss')
            plt.plot(iters, scipy.signal.savgol_filter(self.val_loss, num, 3), '#8B4513', linestyle = '--', linewidth = 2, label='smooth val loss')
        except:
            pass

        plt.grid(True)
        plt.xlabel('Epoch')
        plt.ylabel('Loss')
        plt.legend(loc="upper right")

        plt.savefig(os.path.join(self.save_path, "epoch_loss_" + str(self.time_str) + ".png"))

        plt.cla()
        plt.close("all")
