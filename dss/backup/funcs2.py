import torch.optim as optim
import os,pickle
import torch
import numpy as np
import time
import torch.nn as nn
import sys
from utilities import dataset,loss
from keras.preprocessing.image import ImageDataGenerator,NumpyArrayIterator
import matplotlib.pyplot as plt 
import itertools

def train_seg_network(net,trainloader,init_rate, step_size,gamma,weight_decay,n_train,batch_size):
    # TODO: schedular fix
    optimizer = optim.Adam(net.parameters(),lr=init_rate,weight_decay=weight_decay)
    if weight_decay != 0:
        scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=step_size, gamma=gamma)
    criterion = loss.CrossEntropyLoss2d()
    device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')

    net = net.to(device)
    net = net.train()

    torch.cuda.empty_cache()
    if weight_decay != 0:
        scheduler.step()
    correct = torch.tensor(0)
    loss_sum = 0
    
    for i in range(n_train//batch_size):
        x_imgs, y_imgs = trainloader[i*batch_size:min((i+1)*batch_size,n_train)]
        #x_imgs = torch.from_numpy(x_imgs) ; y_imgs = torch.from_numpy(y_imgs)
        x_imgs = x_imgs.float().to(device) ; y_imgs = y_imgs.float().to(device)
        # zero the parameter gradients
        optimizer.zero_grad()
        y_pred, _ = net(x_imgs)
        l = criterion(y_pred, y_imgs)
        loss_sum += l.item()
        l.backward()
        optimizer.step()
        del x_imgs
        del y_imgs
        torch.cuda.empty_cache()
    print("\tLoss = %d"%(loss_sum))
    net = net.eval()
    return net


def test_seg_network(net,testloader,n_test,batch_size):
    device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
    net.eval()
    correct = torch.tensor(0)

    miou_ = 0
    for i in range(n_test//batch_size):
        x_imgs, y_imgs = testloader[i*batch_size:min((i+1)*batch_size,n_test)]
        try:
            x_imgs = torch.from_numpy(x_imgs) ; y_imgs = torch.from_numpy(y_imgs)
        except:
            pass
        x_imgs = x_imgs.float().to(device) ; y_imgs = y_imgs.float().to(device)

        y_pred , _  = net(x_imgs)
        miou_ += miou(y_pred, y_imgs)
        del x_imgs
        del y_imgs
        torch.cuda.empty_cache()
    miou_ /= n_test
    print("\t Mean Intersection over Union = %3.5f"%(miou_))
    return y_pred 
    # map_



def train_network(net,trainloader,init_rate, step_size,gamma,weight_decay,n_train,batch_size):

    # params = add_weight_decay(net, l2_normal,l2_special,name_special)
    optimizer = optim.SGD(net.parameters(),lr=init_rate, momentum=0.9,weight_decay=weight_decay)
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=step_size, gamma=gamma)
    criterion = nn.CrossEntropyLoss()
    device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')

    net = net.to(device)
    net = net.train()

    torch.cuda.empty_cache()
    scheduler.step()
    correct = torch.tensor(0)
    loss_sum = 0
    if isinstance(trainloader,NumpyArrayIterator):
        for i in range(n_train//batch_size):
            inputs, labels = next(trainloader)
            inputs, labels = torch.from_numpy(inputs), torch.from_numpy(labels)
            labels = labels.long()
            inputs = inputs.to(device)
            labels = labels.to(device)
            
            # zero the parameter gradients
            optimizer.zero_grad()
            print(inputs.shape,"XXXXXXXXX")
            outputs, _ = net(inputs)
            loss = criterion(outputs, labels)
            loss_sum += loss
            loss.backward()
            optimizer.step()
            _, predicted = torch.max(outputs, 1)
            correct = correct + torch.sum(predicted.cuda() == labels)
    elif isinstance(trainloader, dataset.Dataset):
        for i in range(n_train//batch_size):
            inputs, labels = trainloader[i*batch_size:min((i+1)*batch_size,n_train)]
            try:
                labels = torch.from_numpy(labels)
                inputs = torch.from_numpy(inputs)
            except:
                pass 
            labels = labels.long()
            inputs = inputs.to(device)
            labels = labels.to(device)
            # zero the parameter gradients
            optimizer.zero_grad()

            outputs, _ = net(inputs)
            loss = criterion(outputs, labels)
            loss_sum += loss
            loss.backward()
            optimizer.step()
            _, predicted = torch.max(outputs, 1)
            correct = correct.cuda() + torch.sum(predicted == labels).cuda()
    print("\tTrain Accuracy : %d /10000 || Loss = %d"%(correct,loss_sum))
    net = net.eval()
    return net


def test_network(net,testloader,n_test,batch_size):
    device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
    net.eval()
    correct = torch.tensor(0)

    if isinstance(testloader, NumpyArrayIterator):
        for i in range(n_test//batch_size):
            images, labels = next(testloader)
            try:
                labels = torch.from_numpy(labels)
                inputs = torch.from_numpy(inputs)
            except:
                pass 
            
            images = images.to(device)
            labels = labels.to(device)
            outputs, embedding = net(images)
            _, predicted = torch.max(outputs, 1)
            correct = correct + torch.sum(predicted == labels)
            torch.cuda.empty_cache()
    elif isinstance(testloader, dataset.Dataset):
        for i in range(n_test//batch_size):
            images, labels = testloader[i*batch_size:min((i+1)*batch_size,n_test)]
            try:
                labels = torch.from_numpy(labels)
                inputs = torch.from_numpy(inputs)
            except:
                pass 
            images = images.to(device)
            labels = labels.to(device)
            outputs, embedding = net(images)
            _, predicted = torch.max(outputs, 1)
            correct = correct + torch.sum(predicted == labels)
            torch.cuda.empty_cache()
    accuracy = float(correct)/float(n_test)
    print("\tTest Accuracy =",accuracy)
    return accuracy, embedding

def to_seg(ypred):
    """
    Input
        ypred = yprediction of [batchsize，num_class, 512，1024]
    Output
        ypred = (pixel prediction based on prediction [batchsize, 512,1024], class prediction [batchsize,512,1024])

    """
    return torch.max(ypred,1)
    
def miou(ypred, ytrue, n_classes=19):
    """
    Input
        ypred = yprediction of [batchsize，num_class, 512，1024]
        ytrue = target       [batchsize, 512, 1024]
    Output
        mIOU = sum of intersection over union for the batch

    Note this value will be divided by the total number of test at funcs.test_seg_network 

    """
    ypred,_ = to_seg(ypred)
    
    total_iou = 0.0
    for i in range(len(ypred)):
        ypred_tmp = ypred[i]            #(512, 512)
        ytrue_tmp = ytrue[i].squeeze(0)     #(512, 512)

        intersect = [0] * n_classes
        union = [0] * n_classes
        for j in range(n_classes):
            match = (ypred_tmp == j) + (ytrue_tmp == j)
            # intersection 
            it = torch.sum(match == 2).item()
            # union
            un = torch.sum(match > 0).item()
            intersect[j] += it
            union[j] += un

        iou = []
        for k in range(n_classes):
            if union[k] == 0:
                continue
            iou.append(intersect[k] / union[k])

        # img_iou = (sum(iou) / len(iou))
        total_iou += sum(iou)/19

    return total_iou

def bilinear_interpolate(im, point):
    '''
    Given a img interpolate the point (x,y)
    Input:
        img = tensor [C,H,W]
        point = (x,y) coordinates
    Output:
        interpolation result
    '''
    x = point[1]
    y = point[0]

    dtype = torch.cuda.FloatTensor
    dtype_long = torch.cuda.LongTensor

    x0 = torch.floor(x).type(dtype_long)
    x1 = x0 + 1

    y0 = torch.floor(y).type(dtype_long)
    y1 = y0 + 1

    # ensuring that the coordinates are within the grpt4
    x0 = torch.clamp(x0, 0, im.shape[2]-1)
    x1 = torch.clamp(x1, 0, im.shape[2]-1)
    y0 = torch.clamp(y0, 0, im.shape[1]-1)
    y1 = torch.clamp(y1, 0, im.shape[1]-1)

    # extract surrounding points
    pt1 = im[ :, y0, x0 ]
    pt2 = im[ :, y1, x0 ]
    pt3 = im[ :, y0, x1 ]
    pt4 = im[ :, y1, x1 ]

    # weight
    w1 = (x1.type(dtype)-x) * (y1.type(dtype)-y)
    w2 = (x1.type(dtype)-x) * (y-y0.type(dtype))
    w3 = (x-x0.type(dtype)) * (y1.type(dtype)-y)
    w4 = (x-x0.type(dtype)) * (y-y0.type(dtype))

    if (w1 ==0 and w2 ==0 and w3==0 and w4 ==0) or (x1==x0 and y1==y0):
        return im[:,y.long(),x.long()].squeeze(0)
    return (pt1*w1 + pt2*w2 + pt3*w3 + pt4*w4)


def convert(x, downscale):
    '''
    In order to keep the output dimsension of the new scale convolution to be consistent, we need to interpolate points
    Input:
        x = Input feature map/image in scale space [torch.Tensor(B,C,S,H,W)]
        downscale = downscale factor for each scale space [list of length S]; this would be equal to the sigma square value of the gaussian kernel
    Output:
        x = Input feature map downscaled and then interpolated [torch.Tensor(B,C,S,H,W)]
    '''
    out = []
    h,w  = x.shape[-2:]
    shape = x[0,:,0,:,:].shape
    for b in range(x.size()[0]):
        l = []
        for i in range(x.size()[2]):
            s = downscale[i]
            grid = list(itertools.product((np.arange(0,w)* 1/s),(np.arange(0,h)* 1/s)))
            grid = torch.Tensor(grid).cuda()
            add = torch.zeros(shape)
            if h/int(s) == int(h/s):
                pad = 0
            else:
                pad = s//2
            down_x = torch.nn.functional.interpolate(x[b,:,i,:,:].unsqueeze(0), size=(h//s+pad,w//s+pad),mode='bilinear',align_corners=True).squeeze(0)

            # print("Original\n",x[b,:,i,:,:])
            # print("Downsampled\n",down_x,down_x.shape)

            for j,point in enumerate(grid):
                add[:,j//w,j%w]= bilinear_interpolate(down_x,point)
            # print(add,"\n______________")
            l.append(add)
        out.append(torch.stack(l).permute(1,0,2,3))
    out = torch.stack(out)
    assert out.shape == x.shape
    return out
