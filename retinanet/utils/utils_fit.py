import torch
from tqdm import tqdm

from retinanet.utils.utils import get_lr
        
def fit_one_epoch(model_train, model, focal_loss, loss_history, optimizer, epoch, epoch_step, epoch_step_val, gen, gen_val, Epoch, cuda):
    loss        = 0
    val_loss    = 0

    model_train.train()
    print('Start Train')
    with tqdm(total=epoch_step,desc=f'Epoch {epoch + 1}/{Epoch}',postfix=dict,mininterval=0.3) as pbar:
        for iteration, batch in enumerate(gen):
            if iteration >= epoch_step:
                break

            images, targets = batch[0], batch[1]
            with torch.no_grad():
                if cuda:
                    images  = torch.from_numpy(images).type(torch.FloatTensor).cuda()
                    targets = [torch.from_numpy(ann).type(torch.FloatTensor).cuda() for ann in targets]
                else:
                    images  = torch.from_numpy(images).type(torch.FloatTensor)
                    targets = [torch.from_numpy(ann).type(torch.FloatTensor) for ann in targets]
            #----------------------#
            #   清零梯度
            #----------------------#
            optimizer.zero_grad()
            #-------------------#
            #   获得预测结果
            #-------------------#
            _, regression, classification, anchors = model_train(images)
            #-------------------#
            #   计算损失
            #-------------------#
            loss_value, _, _ = focal_loss(classification, regression, anchors, targets, cuda=cuda)

            loss_value.backward()
            torch.nn.utils.clip_grad_norm_(model_train.parameters(), 1e-2)
            optimizer.step()
            
            loss += loss_value.item()
            
            pbar.set_postfix(**{'loss'  : loss / (iteration + 1), 
                                'lr'    : get_lr(optimizer)})
            pbar.update(1)
            loss_history.step(loss / (iteration + 1), (epoch_step * epoch + iteration + 1))

    print('Finish Train')

    model_train.eval()
    print('Start Validation')
    with tqdm(total=epoch_step_val, desc=f'Epoch {epoch + 1}/{Epoch}',postfix=dict,mininterval=0.3) as pbar:
        for iteration, batch in enumerate(gen_val):
            if iteration >= epoch_step_val:
                break
            images, targets = batch[0], batch[1]
            with torch.no_grad():
                if cuda:
                    images  = torch.from_numpy(images).type(torch.FloatTensor).cuda()
                    targets = [torch.from_numpy(ann).type(torch.FloatTensor).cuda() for ann in targets]
                else:
                    images  = torch.from_numpy(images).type(torch.FloatTensor)
                    targets = [torch.from_numpy(ann).type(torch.FloatTensor) for ann in targets]
                #----------------------#
                #   清零梯度
                #----------------------#
                optimizer.zero_grad()
                #-------------------#
                #   获得预测结果
                #-------------------#
                _, regression, classification, anchors = model_train(images)
                #-------------------#
                #   计算损失
                #-------------------#
                loss_value, _, _ = focal_loss(classification, regression, anchors, targets, cuda = cuda)

            val_loss += loss_value.item()
            pbar.set_postfix(**{'val_loss': val_loss / (iteration + 1)})
            pbar.update(1)

    print('Finish Validation')
    
    loss_history.epoch_loss(loss / epoch_step, val_loss / epoch_step_val, epoch+1)
    print('Epoch:'+ str(epoch+1) + '/' + str(Epoch))
    print('Total Loss: %.3f || Val Loss: %.3f ' % (loss / epoch_step, val_loss / epoch_step_val))
    torch.save(model.state_dict(), '%s/ep%03d-loss%.3f-val_loss%.3f.pth' % (loss_history.log_dir, epoch + 1, loss / epoch_step, val_loss / epoch_step_val))
