import argparse
import sys
import time
import warnings
import colorsys
sys.path.append('./')  # to run '$ python *.py' files in subdirectories

import torch
import torch.nn as nn
from torch.utils.mobile_optimizer import optimize_for_mobile

import models
from models.experimental import attempt_load, End2End
from utils.activations import Hardswish, SiLU
from utils.general import set_logging, check_img_size
from utils.torch_utils import select_device
from utils.add_nms import RegisterNMS
import importlib
import onnxruntime as ort
import numpy as np
import cv2
from glob import glob
import os
from PIL import ImageDraw, ImageFont

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--weights', type=str, 
                        default='work_dirs\\lane_yolov5\\best_epoch_weights.pth', help='weights path')
    parser.add_argument('--img-size', nargs='+', type=int, default=[640, 640], help='image size')  # height, width
    parser.add_argument('--batch-size', type=int, default=1, help='batch size')
    parser.add_argument('--dynamic', default=True, action='store_true', help='dynamic ONNX axes')
    parser.add_argument('--dynamic-batch', action='store_true', help='dynamic batch onnx for tensorrt and onnx-runtime')
    parser.add_argument('--grid', action='store_true', help='export Detect() layer grid')
    parser.add_argument('--end2end', action='store_true', help='export end2end onnx')
    parser.add_argument('--max-wh', type=int, default=None, help='None for tensorrt nms, int value for onnx-runtime nms')
    parser.add_argument('--topk-all', type=int, default=100, help='topk objects for every images')
    parser.add_argument('--iou-thres', type=float, default=0.45, help='iou threshold for NMS')
    parser.add_argument('--conf-thres', type=float, default=0.25, help='conf threshold for NMS')
    parser.add_argument('--device', default='cpu', help='cuda device, i.e. 0 or 0,1,2,3 or cpu')
    parser.add_argument('--simplify', default=True, action='store_true', help='simplify onnx model')
    parser.add_argument('--include-nms', action='store_true', help='export end2end onnx')
    parser.add_argument('--fp16', action='store_true', help='CoreML FP16 half-precision export')
    parser.add_argument('--int8', action='store_true', help='CoreML INT8 quantization')
    parser.add_argument('--config', type=str, default="configs.yolov5_base" ,help = 'Path to config .opt file. ')

    opt = parser.parse_args()
    opt.img_size *= 2 if len(opt.img_size) == 1 else 1  # expand
    opt.dynamic = opt.dynamic and not opt.end2end
    opt.dynamic = False if opt.dynamic_batch else opt.dynamic
    conf = importlib.import_module(opt.config).get_opts(Train=False)
    for key, value in vars(conf).items():
        setattr(opt, key, value)
    # print(opt)
    set_logging()
    t = time.time()

    # Load PyTorch model
    device = select_device(opt.device)

    # Input
    img = torch.zeros(opt.batch_size, 3, *opt.img_size).to(device)  # image size(1,3,320,192) iDetection

    print("Load model.")
    model, _  = models.get_model(opt)
    model.load_state_dict(torch.load(opt.weights, map_location=device))
    print("Load model done.") 

    y = model(img)  # dry run
    if opt.include_nms:
        model.model[-1].include_nms = True
        y = None

    if False:
        # ONNX export
        try:
            import onnx

            print('\nStarting ONNX export with onnx %s...' % onnx.__version__)
            f = opt.weights.replace('.pth', '.onnx')  # filename
            model.eval()
            output_names = ['classes', 'boxes'] if y is None else ['output']
            dynamic_axes = None
            if opt.dynamic:
                dynamic_axes = {'images': {0: 'batch', 2: 'height', 3: 'width'},  # size(1,3,640,640)
                'output': {0: 'batch', 2: 'y', 3: 'x'}}
            if opt.dynamic_batch:
                opt.batch_size = 'batch'
                dynamic_axes = {
                    'images': {
                        0: 'batch',
                    }, }
                if opt.end2end and opt.max_wh is None:
                    output_axes = {
                        'num_dets': {0: 'batch'},
                        'det_boxes': {0: 'batch'},
                        'det_scores': {0: 'batch'},
                        'det_classes': {0: 'batch'},
                    }
                else:
                    output_axes = {
                        'output': {0: 'batch'},
                    }
                dynamic_axes.update(output_axes)
            if opt.grid:
                if opt.end2end:
                    print('\nStarting export end2end onnx model for %s...' % 'TensorRT' if opt.max_wh is None else 'onnxruntime')
                    model = End2End(model,opt.topk_all,opt.iou_thres,opt.conf_thres,opt.max_wh,device,len(labels))
                    if opt.end2end and opt.max_wh is None:
                        output_names = ['num_dets', 'det_boxes', 'det_scores', 'det_classes']
                        shapes = [opt.batch_size, 1, opt.batch_size, opt.topk_all, 4,
                                opt.batch_size, opt.topk_all, opt.batch_size, opt.topk_all]
                    else:
                        output_names = ['output']
                else:
                    model.model[-1].concat = True

            input_names = ['images']
            torch.onnx.export(model, img, f, verbose=False, opset_version=12, input_names=input_names,
                            output_names=output_names,
                            dynamic_axes=dynamic_axes)

            # Checks
            onnx_model = onnx.load(f)  # load onnx model
            onnx.checker.check_model(onnx_model)  # check onnx model

            if opt.end2end and opt.max_wh is None:
                for i in onnx_model.graph.output:
                    for j in i.type.tensor_type.shape.dim:
                        j.dim_param = str(shapes.pop(0))

            graph = onnx.helper.printable_graph(onnx_model.graph)
            # print(graph)  # print a human readable model         
            # onnx_graph_path = opt.weights.replace(".pth", ".txt")
            # with open(onnx_graph_path, "w", encoding="utf-8") as f:
            #     f.write(graph)
            

            if opt.simplify:
                try:
                    import onnxsim

                    print('\nStarting to simplify ONNX...')
                    onnx_model, check = onnxsim.simplify(onnx_model)
                    assert check, 'assert check failed'
                except Exception as e:
                    print(f'Simplifier failure: {e}')

            # print(onnx.helper.printable_graph(onnx_model.graph))  # print a human readable model
            f = opt.weights.replace('.pth', '_simp.onnx')  # filename
            onnx.save(onnx_model, f)
            print('ONNX export success, saved as %s' % f)

            if opt.include_nms:
                print('Registering NMS plugin for ONNX...')
                mo = RegisterNMS(f)
                mo.register_nms()
                mo.save(f)

        except Exception as e:
            print('ONNX export failure: %s' % e)

        # Finish
        print('\nExport complete (%.2fs). Visualize with https://github.com/lutzroeder/netron.' % (time.time() - t))

    # Test forward with onnx session (test image) 
    for sample_image in glob("test_images/*.jpg") :
        image = cv2.imread(sample_image)
        image_shape = np.array(np.shape(image)[0:2])

        f = "work_dirs\\lane_yolov5\\best_epoch_weights_simp.onnx"
        ort_session = ort.InferenceSession(f)        
        new_image       = cv2.resize(image, opt.img_size, interpolation=cv2.INTER_CUBIC)
        new_image       = np.expand_dims(np.transpose(np.array(new_image, dtype=np.float32)/255, (2, 0, 1)),0)

        outputs = ort_session.run(
            None, # ['output']
            {"images": new_image},
        )

        from det_model.yolov5.utils.utils_bbox import DecodeBox
        bbox_util = DecodeBox(opt.anchors, opt.num_classes, opt.img_size, opt.anchors_mask)

        #---------------------------------------------------#
        #   画框设置不同的颜色
        #---------------------------------------------------#
        hsv_tuples = [(x / opt.num_classes, 1., 1.) for x in range(opt.num_classes)]
        opt.colors = list(map(lambda x: colorsys.hsv_to_rgb(*x), hsv_tuples))
        opt.colors = list(map(lambda x: (int(x[0] * 255), int(x[1] * 255), int(x[2] * 255)), opt.colors))

        outputs = [torch.from_numpy(o) for o in outputs]
        outputs = bbox_util.decode_box(outputs)
        results = bbox_util.non_max_suppression(torch.cat(outputs, 1), opt.num_classes, opt.img_size, 
                            image_shape, False, conf_thres = 0.5, nms_thres = 0.3)

        top_label   = np.array(results[0][:, 6], dtype = 'int32')
        top_conf    = results[0][:, 4] * results[0][:, 5]
        top_boxes   = results[0][:, :4]

        #---------------------------------------------------------#
        #   设置字体与边框厚度
        #---------------------------------------------------------#
        font        = ImageFont.truetype(font='model_data/simhei.ttf', size=np.floor(3e-2 * image.shape[1] + 0.5).astype('int32'))
        thickness   = int(max((image.shape[0] + image.shape[1]) // np.mean(opt.input_shape), 1))       
        #---------------------------------------------------------#
        #   图像绘制
        #---------------------------------------------------------#
        for i, c in list(enumerate(top_label)):
            predicted_class = opt.class_names[int(c)]
            box             = top_boxes[i]
            score           = top_conf[i]

            top, left, bottom, right = box

            top     = max(0, np.floor(top).astype('int32'))
            left    = max(0, np.floor(left).astype('int32'))
            bottom  = min(image.shape[1], np.floor(bottom).astype('int32'))
            right   = min(image.shape[0], np.floor(right).astype('int32'))

            label = '{} {:.2f}'.format(predicted_class, score)
            draw = ImageDraw.Draw(image)
            label_size = draw.textsize(label, font)
            label = label.encode('utf-8')
            print(label, top, left, bottom, right)
            
            if top - label_size[1] >= 0:
                text_origin = np.array([left, top - label_size[1]])
            else:
                text_origin = np.array([left, top + 1])

            for i in range(thickness):
                draw.rectangle([left + i, top + i, right - i, bottom - i], outline=opt.colors[c])
            draw.rectangle([tuple(text_origin), tuple(text_origin + label_size)], fill=opt.colors[c])
            draw.text(text_origin, str(label,'UTF-8'), fill=(0, 0, 0), font=font)
        
        # RGBtoBGR滿足opencv顯示格式
        frame = cv2.cvtColor(image,cv2.COLOR_RGB2BGR)
        frame.show()


