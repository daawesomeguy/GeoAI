from __future__ import print_function, division


from torch.utils.tensorboard import SummaryWriter

import logging,random,shutil
import torch
import torch.nn as nn
import torch.optim as optim
from torch.autograd import Variable
import numpy as np
import torchvision
from torchvision import datasets, models, transforms
import time
import copy
import os
import logging
from PIL import ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True

from torchvision.models import resnet50, ResNet50_Weights,ResNet101_Weights

from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import torch.nn.functional as F
from lib2to3.pgen2 import driver
from selenium import webdriver
import time
import sys,json
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import pickle
options = Options()
options.add_experimental_option("useAutomationExtension", False)
options.add_experimental_option("excludeSwitches",["enable-automation"])
driver = webdriver.Chrome(executable_path=r"C:\Users\Jack\Downloads\chromedriver_win32\chromedriver.exe", options=options)
cookies = pickle.load(open(r"C:\Users\Jack\Downloads\cookies.pkl", "rb"))
def rotate_canvas():
        main = driver.find_element_by_tag_name('main')
        for _ in range(0,5):
            action = webdriver.common.action_chains.ActionChains(driver)
            action.move_to_element(main) \
                .click_and_hold(main) \
                .move_by_offset(118, 0) \
                .release(main) \
                .perform()

training=False
BASE_LR = 0.01
EPOCH_DECAY = 10
DECAY_WEIGHT = 0.8

NUM_CLASSES = 59
DATA_DIR = "C:\\Users\\Jack\\Downloads\\data\\" 
BATCH_SIZE = 32

CUDA_DEVICE = 0


use_gpu = True
print(torch.cuda.is_available()) # Check that CUDA works
print(torch.cuda.device_count())
if use_gpu:
    device=torch.device('cuda:0')

count=0
#normalization from alexnet papers
data_transforms = {
    'train': transforms.Compose([
        transforms.RandomResizedCrop((350,350),scale=(0.5,1), ratio=(0.6,1.4)),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ]),
    'val': transforms.Compose([
        transforms.Resize(350),
        transforms.CenterCrop(350),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ]),
    'test': transforms.Compose([
        transforms.Resize(350),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])  
    ]),
}




data_dir = DATA_DIR

dsets = {x: datasets.ImageFolder(os.path.join(data_dir, x), data_transforms[x])
        for x in ['train', 'val']}
dset_loaders = {x: torch.utils.data.DataLoader(dsets[x], batch_size=BATCH_SIZE,
                                            shuffle=True,pin_memory=True,num_workers=4)
                for x in ['train', 'val']}
dset_sizes = {x: len(dsets[x]) for x in ['train', 'val']}
dset_classes = dsets['train'].classes


def train_model(model, criterion, optimizer, lr_scheduler, num_epochs=50):
    since = time.time()
    best_model = model
    best_acc = 0.0
    for epoch in range(num_epochs):
        print('Epoch {}/{}'.format(epoch, num_epochs - 1))
        print('-' * 10)
        
        for phase in ['train', 'val']:
            if phase == 'train':
                mode='train'
                optimizer = lr_scheduler(optimizer, epoch)
                model.train()  
            else:
                model.eval()
                torch.no_grad()
                mode='val'

            running_loss = 0.0
            running_corrects = 0

            counter=0
            #print(len(dset_loaders[phase]))
            for i,data in enumerate(dset_loaders[phase]):
                inputs, labels = data
                inputs, labels = inputs.to(device), labels.to(device)
                #print(str(i)+'/'+str(len(dset_loaders[phase]))+'epoch:'+str(epoch))
                '''
                if use_gpu:
                    try:
                        inputs, labels = Variable(inputs.float().cuda()),                             
                        Variable(labels.long().cuda())
                    except Exception as e:
                        print(e)
                        print(inputs)
                        print('labels:')
                        print(labels)
                else:
                    inputs, labels = Variable(inputs), Variable(labels)
                '''
            
                optimizer.zero_grad(set_to_none=True)
                with torch.cuda.amp.autocast():
                    outputs = model(inputs)
                    loss = criterion(outputs, labels)
                _, preds = torch.max(outputs.data, 1)
                counter+=1
                
                #print(phase)
                
                if phase == 'train':
                    #writer.add_scalar("Loss/train", loss, i)
                    #loss.backward()
                    scaler.scale(loss).backward()
                    # print('done loss backward')
                    #optimizer.step()
                    scaler.step(optimizer)
                    # print('done optim')
                    scaler.update()
                #else:
                    #writer.add_scalar("Loss/val", loss, i)
                try:
                    # running_loss += loss.data[0]
                    running_loss += loss.item()
                    # print(labels.data)
                    #print(preds)
                    running_corrects += torch.sum(preds == labels.data)
                    #print('running correct =',running_corrects)

                except Exception as e:
                    print(e)
            print('trying epoch loss')
            epoch_loss = running_loss / dset_sizes[phase]
            epoch_acc = running_corrects.item() / float(dset_sizes[phase])
            
            print('{} Loss: {:.4f} Acc: {:.4f}'.format(
                phase, epoch_loss, epoch_acc))
            

            if phase == 'val':
                if epoch_acc > best_acc:
                    best_acc = epoch_acc
                    best_model = copy.deepcopy(model)
                    writer.add_scalar("Loss/epochval", epoch_loss, epoch)
                    print('new best accuracy = ',best_acc)
            else:
                writer.add_scalar("Loss/epoch", epoch_loss, epoch)
    time_elapsed = time.time() - since
    print('Training complete in {:.0f}m {:.0f}s'.format(
        time_elapsed // 60, time_elapsed % 60))
    print('Best val Acc: {:4f}'.format(best_acc))
    print('returning and looping back')
    return best_model
    
def exp_lr_scheduler(optimizer, epoch, init_lr=BASE_LR, lr_decay_epoch=EPOCH_DECAY):
    """Decay learning rate by a factor of DECAY_WEIGHT every lr_decay_epoch epochs."""
    lr = init_lr * (DECAY_WEIGHT**(epoch // lr_decay_epoch))

    if epoch % lr_decay_epoch == 0:
        print('LR is set to {}'.format(lr))

    for param_group in optimizer.param_groups:
        param_group['lr'] = lr

    return optimizer

#resnet 18 or 50 or 101
writer = SummaryWriter()
model_ft = models.resnet101(weights=ResNet101_Weights.DEFAULT)


num_ftrs = model_ft.fc.in_features
model_ft.fc = nn.Linear(num_ftrs, NUM_CLASSES)
model_ft.to(device)
model_ft.fc.register_forward_hook(lambda m, inp, out: F.dropout(out, p=0.5, training=m.training))
criterion = nn.CrossEntropyLoss()

if use_gpu:
    criterion.to(device)
    #model_ft.cuda()

optimizer_ft = optim.SGD(model_ft.parameters(), lr=0.01,momentum=0.9, weight_decay=0.0001,nesterov=True)
scaler = torch.cuda.amp.GradScaler()
#checkpoint = torch.load(PATH)
#model_ft.load_state_dict(checkpoint['model_state_dict'])
#optimizer_ft.load_state_dict(checkpoint['optimizer_state_dict'])
#epoch = checkpoint['epoch']
#loss = checkpoint['loss']
torch.backends.cudnn.benchmark = True
#model_ft.eval()
# - or -
#model_ft.train()

if training==True:
    model_ft = train_model(model_ft, criterion, optimizer_ft, exp_lr_scheduler,
                    num_epochs=50)
    writer.flush()
    writer.close()
    torch.save(model_ft.state_dict(), "C:\\Users\\Jack\\Downloads\\fine_tuned_best_model.pt")
else:
    model_ft.load_state_dict(torch.load("C:\\Users\\Jack\\Downloads\\fine_tuned_best_model.pt"))
    model_ft.eval().type(torch.FloatTensor)
    #model_ft.to(device)
    
    for i in range(5):
        url='https://www.geoguessr.com/game/fTknKMrNpT6QnQuF'
        driver.get(url)
        for cookie in cookies:
            driver.add_cookie(cookie)
        driver.get(url)
        driver.fullscreen_window()
        time.sleep(0.2)
        for css in ['#__next > div > div > main > div > div > div > div > div > div > div > div:nth-child(1) > div > div.gmnoprint > svg > path:nth-child(1)','#__next > div > div > main > div > div > div > div > div > div > div > div:nth-child(1) > div > div.gmnoprint > svg > path:nth-child(3)','#__next > div > div > main > div > div > div > div > div > div > div > div:nth-child(1) > div > div.gmnoprint > svg > path:nth-child(2)','#__next > div > div > main > div > div > div > div > div > div > div > div:nth-child(1) > div > div.gmnoprint > svg > path:nth-child(2)','#__next > div > div > main > div > div > div > div > div > div > div > div:nth-child(1) > div > div.gmnoprint > svg > path:nth-child(1)','#__next > div > div > main > div > div > div.game-layout__top-hud','#__next > div > div > main > div > div > aside','#__next > div > div > main > div > div > div.game-layout__status','#__next > div > div > main > div > div > div.game-layout__guess-map']:
            element=driver.find_element(By.CSS_SELECTOR,css)
            driver.execute_script("""
            var element = arguments[0];
            element.parentNode.removeChild(element);
            """, element)
        time.sleep(1)
        driver.find_element(By.CSS_SELECTOR,"#__next > div > div > main > div > div > div.game-layout__panorama > div > div > div > div > div:nth-child(1) > div > div:nth-child(10) > div > canvas").screenshot("C:\\Users\\Jack\\Downloads\\data\\test\\FO\\testimage.png")        
        data= torch.utils.data.DataLoader(datasets.ImageFolder(os.path.join(data_dir, 'test'), data_transforms['test']), batch_size=None)
        for i in data:

            inputs=i[0]
            inputs.type(torch.FloatTensor).to(device)

            output=model_ft(inputs.unsqueeze(0))

            sm = torch.nn.Softmax()
            probabilities = sm(output) 
            print(probabilities)
            code=dset_classes[output.detach().numpy().argmax()]
            
            f=open("C:\\Users\\Jack\\Downloads\\ISO-3166-Countries-with-Regional-Codes-master\\ISO-3166-Countries-with-Regional-Codes-master\\all\\all.json")
            codes = json.load(f)
            for i in codes:
                if code==i['alpha-2']:
                    print(i['name'])
                    newcode=i['name']
        driver.execute_script(f'alert("{newcode}");')
        time.sleep(10)
        driver.get(url)
        WebDriverWait(driver, 100).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#__next > div > div > main > div.result-layout_root__NfX12 > div > div.result-layout_bottom__qLPd2 > div > div:nth-child(1) > div > div.round-result_actions__5j26U > button"))).click()
