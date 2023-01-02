import argparse,json,random,os
import numpy as np
import torch
import torch.backends.cudnn as cudnn
import torchvision as tv

import logging
import sys
import importlib
from torch.utils.tensorboard import SummaryWriter
from trainer import Trainer


def main():    
    # Load options
    parser = argparse.ArgumentParser(description='Attribute Learner')
    # parser.add_argument('--config', type=str, default="configs.ssd_base" 
    # parser.add_argument('--config', type=str, default="configs.retina_base" 
    # parser.add_argument('--config', type=str, default="configs.centernet_base" 
    # parser.add_argument('--config', type=str, default="configs.fasterRcnn_base" 
    # parser.add_argument('--config', type=str, default="configs.yolov3_base" 
    # parser.add_argument('--config', type=str, default="configs.yolov4_base" 
    # parser.add_argument('--config', type=str, default="configs.yolov5_base" 
    parser.add_argument('--config', type=str, default="configs.yolox_base" 
                        ,help = 'Path to config .opt file. Leave blank if loading from opts.py')
    parser.add_argument("--local_rank", type=int, default=0, help="local_rank")    
    parser.add_argument("--distributed", type=bool, default=False, help="distributed")                       
    
    conf = parser.parse_args() 
   
    opt = importlib.import_module(conf.config).get_opts()
    for key, value in vars(conf).items():
        # opt.add_argument(key, default=value)
        # opt.key = value
        setattr(opt, key, value)
    
    logging.info('===Options==') 
    d=vars(opt)

    with open(os.path.join(d["out_path"], 'commandline_args.txt'), 'w') as f:        
        for key, value in d.items():
            if key in ["train_lines", "val_lines"]: continue
            num_space = 25 - len(key)
            try:
                f.write(key + " = " + str(value) + "\n")
            except Exception as e :
                pass

    for key, value in d.items():
        if key in ["train_lines", "val_lines"]: continue
        num_space = 25 - len(key)
        try:
            logging.info(": " + key + " " * num_space + str(value))
        except Exception as e:
            print(e)

    # Fix seed
    random.seed(opt.manual_seed)
    np.random.seed(opt.manual_seed)
    torch.manual_seed(opt.manual_seed)
    torch.cuda.manual_seed_all(opt.manual_seed)
    cudnn.benchmark = True
    
    # Create working directories
    try:
        logging.info( 'Directory {} was successfully created.'.format(opt.out_path))
                   
    except OSError:
        logging.info( 'Directory {} already exists.'.format(opt.out_path))
        pass

    # Training
    t = Trainer(opt)
    t.train()

    print()

if __name__ == '__main__':
    main()    