import sys
sys.path.append(".")

import argparse, os, json
import torch
import torchvision as tv
from torch.utils.tensorboard import SummaryWriter
from utils.tools import init_logging
import importlib
from utils.helpers import get_data_path, get_classes  

   
def get_opts(Train=True):
    opt = argparse.Namespace()  

    #the train data, you need change.
    opt.data_root = '/home/leyan/DataSet/'
    # opt.data_root = 'D://WorkSpace//JupyterWorkSpace//DataSet//'
  
    opt.out_root = 'work_dirs/'
    opt.exp_name = 'lane'
    """
    [ AsianTraffic, bdd, coco, voc, lane, widerperson, MosquitoContainer ]
    """
    # get annotation file in current seting
    # importlib.import_module("annotation.{}".format(opt.exp_name)).get_annotation(opt.data_root) 

    opt.data_path = get_data_path(opt.data_root, opt.exp_name)
    opt.classes_path = 'model_data/{}_classes.txt'.format(opt.exp_name)

    #----------------------------------------------------#
    #   獲得圖片路徑和標簽
    #----------------------------------------------------#
    opt.train_annotation_path   = os.path.join(opt.data_path, "Detection//train.txt")
    opt.val_annotation_path   = os.path.join(opt.data_path, "Detection//val.txt") 
    #---------------------------#
    #   讀取數據集對應的txt
    #---------------------------#
    with open(opt.train_annotation_path) as f:
        opt.train_lines = f.readlines()
    with open(opt.val_annotation_path) as f:
        opt.val_lines   = f.readlines()
    opt.num_train   = len(opt.train_lines)
    opt.num_val     = len(opt.val_lines)
    #----------------------------------------------------#
    #   獲取classes和anchor
    #----------------------------------------------------#
    opt.class_names, opt.num_classes = get_classes(opt.classes_path)    
    #############################################################################################


    #############################################################################################    
    opt.net = 'yolov4'     # [centernet, faster_rcnn, retinanet, ssd, yolov3, yolov4, yolov5, yolox]
    # opt.model_path      = 'model_data/weight/yolo4_weights.pth'
    opt.model_path      = ''
    opt.input_shape     = [416, 416]  
    opt.pretrained      = True
    opt.IM_SHAPE = (opt.input_shape[0], opt.input_shape[1], 3)
    #------------------------------------------------------#
    #   可用于设定先验框的大小，默认的anchors_size
    #   是根据voc数据集设定的，大多数情况下都是通用的！
    #   如果想要检测小物体，可以修改anchors_size
    #   一般调小浅层先验框的大小就行了！因为浅层负责小物体检测！
    #   比如anchors_size = [21, 45, 99, 153, 207, 261, 315]
    #------------------------------------------------------#
    opt.anchors_path    = 'det_model/yolov4/yolo_anchors.txt'
    opt.anchors_mask    = [[6, 7, 8], [3, 4, 5], [0, 1, 2]]
    get_anchors = importlib.import_module("det_model.{}.utils.utils".format(opt.net)).get_anchors
    opt.anchors, opt.num_anchors     = get_anchors(opt.anchors_path)
    #------------------------------------------------------#
    #   Yolov4的tricks應用
    #   mosaic 馬賽克數據增強 True or False 
    #   實際測試時mosaic數據增強並不穩定，所以默認為False
    #   Cosine_lr 余弦退火學習率 True or False
    #   label_smoothing 標簽平滑 0.01以下一般 如0.01、0.005
    #------------------------------------------------------#
    opt.mosaic              = True    
    opt.Cosine_lr           = False
    opt.label_smoothing     = 0
    #----------------------------------------------------#
    #----------------------------------------------------#
    #   凍結階段訓練參數
    #   此時模型的主幹被凍結了，特征提取網絡不發生改變
    #   占用的顯存較小，僅對網絡進行微調
    #----------------------------------------------------#
    opt.ngpu = 2
    opt.Init_Epoch          = 0
    opt.Freeze_Epoch    = 50 #50
    opt.Freeze_batch_size   = int(8/2)
    opt.Freeze_lr           = 1e-3
    #----------------------------------------------------#
    #   解凍階段訓練參數
    #   此時模型的主幹不被凍結了，特征提取網絡會發生改變
    #   占用的顯存較大，網絡所有的參數都會發生改變
    #----------------------------------------------------#
    opt.UnFreeze_Epoch  = 100 #100
    opt.Unfreeze_batch_size = int(4/1)
    opt.Unfreeze_lr         = 1e-4
    #------------------------------------------------------#
    #   是否進行凍結訓練，默認先凍結主幹訓練後解凍訓練。
    #------------------------------------------------------#
    opt.Freeze_Train        = True
    #-------------------------------------------------------------------#
    #   如果不冻结训练的话，直接设置batch_size为Unfreeze_batch_size
    #-------------------------------------------------------------------#
    opt.batch_size = opt.Freeze_batch_size if opt.Freeze_Train else opt.Unfreeze_batch_size
    #------------------------------------------------------------------#
    #   其它训练参数：学习率、优化器、学习率下降有关
    #------------------------------------------------------------------#
    #------------------------------------------------------------------#
    #   Init_lr         模型的最大学习率
    #   Min_lr          模型的最小学习率，默认为最大学习率的0.01
    #------------------------------------------------------------------#
    opt.Init_lr             = 1e-2
    opt.Min_lr              = opt.Init_lr * 0.01
    #------------------------------------------------------------------#
    #   lr_decay_type   使用到的学习率下降方式，可选的有step、cos
    #------------------------------------------------------------------#
    opt.lr_decay_type       = "cos"
    opt.weight_decay    = 5e-4
    opt.gamma           = 0.94
    opt.optimizer_type      = "sgd"
    opt.momentum            = 0.937
    #------------------------------------------------------#
    #   是否提早結束。
    #------------------------------------------------------#
    opt.Early_Stopping  = True
    #------------------------------------------------------#
    #   主幹特征提取網絡特征通用，凍結訓練可以加快訓練速度
    #   也可以在訓練初期防止權值被破壞。
    #   Init_Epoch為起始世代
    #   Freeze_Epoch為凍結訓練的世代
    #   UnFreeze_Epoch總訓練世代
    #   提示OOM或者顯存不足請調小Batch_size
    #------------------------------------------------------#
    opt.UnFreeze_flag = False
    #-------------------------------------------------------------------#
    #   如果不冻结训练的话，直接设置batch_size为Unfreeze_batch_size
    #-------------------------------------------------------------------#
    opt.batch_size = opt.Freeze_batch_size if opt.Freeze_Train else opt.Unfreeze_batch_size
    opt.end_epoch = opt.Freeze_Epoch if opt.Freeze_Train else opt.UnFreeze_Epoch
    #------------------------------------------------------#
    #   用於設置是否使用多線程讀取數據
    #   開啟後會加快數據讀取速度，但是會占用更多內存
    #   內存較小的電腦可以設置為2或者0  
    #   sync_bn     是否使用sync_bn，DDP模式多卡可用
    #   fp16        是否使用混合精度训练
    #               可减少约一半的显存、需要pytorch1.7.1以上
    #   distributed     用于指定是否使用单机多卡分布式运行
    #                   终端指令仅支持Ubuntu。CUDA_VISIBLE_DEVICES用于在Ubuntu下指定显卡。
    #                   Windows系统下默认使用DP模式调用所有显卡，不支持DDP。
    #   DP模式：
    #       设置            distributed = False
    #       在终端中输入    CUDA_VISIBLE_DEVICES=0,1 python train.py
    #   DDP模式：
    #       设置            distributed = True
    #       在终端中输入    CUDA_VISIBLE_DEVICES=0,1 python -m torch.distributed.launch --nproc_per_node=2 train.py
    #------------------------------------------------------#
    opt.num_workers         = 4
    opt.Cuda                = True
    opt.distributed         = True
    opt.sync_bn             = True
    opt.fp16                = True
    #############################################################################################
    opt.debug = 0
    ### Other ###
    opt.manual_seed = 704
    opt.log_batch_interval = 10
    opt.log_checkpoint = 10
    #############################################################################################
    opt.out_path = os.path.join(opt.out_root, "{}_{}".format(opt.exp_name, opt.net))
    if Train:
        opt.writer = SummaryWriter(log_dir=os.path.join(opt.out_path, "tensorboard"))
        init_logging(0, opt.out_path)    
 
    return opt

if __name__ == "__main__":    
    get_opts(Train=False)