'''
usage: python gen_diff.py -h
'''

from __future__ import print_function

import argparse
import os
import time

from keras.datasets import mnist
from keras.layers import Input
from keras.utils import to_categorical
from scipy.io import loadmat
from scipy.misc import imsave

from SVHN_deepxplore.model.ModelA import ModelA
from SVHN_deepxplore.model.ModelB import ModelB
from SVHN_deepxplore.model.ModelC import ModelC
from configs import bcolors
from utils import *

# read the parameter
# argument parsing
parser = argparse.ArgumentParser(description='Main function for difference-inducing input generation in MNIST dataset')
parser.add_argument('--transformation', help="realistic transformation type", choices=['light', 'occl', 'blackout'],default='occl')
parser.add_argument('--weight_diff', help="weight hyperparm to control differential behavior", type=float,default=0.5)
parser.add_argument('--weight_nc', help="weight hyperparm to control neuron coverage", type=float,default=0.5)
parser.add_argument('--neuron_to_cover_num', help="number of neuron to cover", type=int, default=5)
parser.add_argument('--step', help="step size of gradient descent", type=float,default=0.01)
parser.add_argument('--grad_iterations', help="number of iterat-ions of gradient descent", type=int, default=100)
parser.add_argument('--threshold', help="threshold for determining neuron activated", type=float,default=0.5)
parser.add_argument('-t', '--target_model', help="target model that we want it predicts differently",
                    choices=[0, 1, 2], default=1, type=int)
parser.add_argument('-sp', '--start_point', help="occlusion upper left corner coordinate", default=(0, 0), type=tuple)
parser.add_argument('-occl_size', '--occlusion_size', help="occlusion size", default=(30, 30), type=tuple)


args = parser.parse_args()

# input image dimensions

img_rows, img_cols = 32, 32
img_chn = 3

input_shape = (img_rows, img_cols, img_chn)
# define input tensor as a placeholder
input_tensor = Input(shape=input_shape)

# load multiple models sharing same input tensor
model1 = ModelA(input_tensor=input_tensor)
model2 = ModelB(input_tensor=input_tensor)
model3 = ModelC(input_tensor=input_tensor)


# init coverage table
model_layer_dict1, model_layer_dict2, model_layer_dict3 = init_coverage_tables(model1, model2, model3)

img_dir = 'seed_selection/seeds_50_random'
save_dir = './generated_inputs/' + '/'
if os.path.exists(save_dir):
    for i in os.listdir(save_dir):
        path_file = os.path.join(save_dir, i)
        if os.path.isfile(path_file):
            os.remove(path_file)

if not os.path.exists(save_dir):
    os.makedirs(save_dir)

img_paths = os.listdir(img_dir)
img_num = len(img_paths)
# ==============================================================================================
# start gen inputs
total_time = 0
total_norm = 0
adversial_num = 0
total_perturb_adversial = 0
for i in range(img_num):
    start_time = time.clock()

    img_path = os.path.join(img_dir, img_paths[i])

    img_name = img_paths[i].split('.')[0]

    mannual_label = int(img_name.split('_')[1])

    # print(img_path)

    gen_img = preprocess_image(img_path)


    orig_img = gen_img.copy()
    # first check if input already induces differences
    label1, label2, label3 = np.argmax(model1.predict(gen_img)[0]), np.argmax(model2.predict(gen_img)[0]), np.argmax(model3.predict(gen_img)[0])

    if not label1 == label2 == label3:
        adversial_num += 1
        print(bcolors.OKGREEN + 'input already causes different outputs: {}, {}, {}'.format(label1, label2,
                                                                                            label3) + bcolors.ENDC)
        update_coverage(gen_img, model1, model_layer_dict1, args.threshold)
        update_coverage(gen_img, model2, model_layer_dict2, args.threshold)
        update_coverage(gen_img, model3, model_layer_dict3, args.threshold)

        print(bcolors.OKGREEN + 'covered neurons percentage %d neurons %.3f, %d neurons %.3f, %d neurons %.3f'
              % (len(model_layer_dict1), neuron_covered(model_layer_dict1)[2], len(model_layer_dict2),
                 neuron_covered(model_layer_dict2)[2], len(model_layer_dict3),
                 neuron_covered(model_layer_dict3)[2]) + bcolors.ENDC)
        averaged_nc = (neuron_covered(model_layer_dict1)[0] + neuron_covered(model_layer_dict2)[0] +
                       neuron_covered(model_layer_dict3)[0]) / float(
            neuron_covered(model_layer_dict1)[1] + neuron_covered(model_layer_dict2)[1] +
            neuron_covered(model_layer_dict3)[
                1])
        print(bcolors.OKGREEN + 'averaged covered neurons %.3f' % averaged_nc + bcolors.ENDC)

        gen_img_deprocessed = deprocess_image(gen_img)

        # save the result to disk
        imsave('./generated_inputs/' + 'already_differ_' + str(label1) + '_' + str(
            label2) + '_' + str(label3) + '.png', gen_img_deprocessed)
        continue

    # if all label agrees
    orig_label = label1
    # layer_name1, index1 = neuron_to_cover(model_layer_dict1)
    # layer_name2, index2 = neuron_to_cover(model_layer_dict2)
    # layer_name3, index3 = neuron_to_cover(model_layer_dict3)

    # construct joint loss function
    if args.target_model == 0:
        loss1 = -args.weight_diff * K.mean(model1.get_layer('global_average_pooling2d_1').output[..., orig_label])
        loss2 = K.mean(model2.get_layer('global_average_pooling2d_2').output[..., orig_label])
        loss3 = K.mean(model3.get_layer('global_average_pooling2d_3').output[..., orig_label])
    elif args.target_model == 1:
        loss1 = K.mean(model1.get_layer('global_average_pooling2d_1').output[..., orig_label])
        loss2 = -args.weight_diff * K.mean(model2.get_layer('global_average_pooling2d_2').output[..., orig_label])
        loss3 = K.mean(model3.get_layer('global_average_pooling2d_3').output[..., orig_label])
    elif args.target_model == 2:
        loss1 = K.mean(model1.get_layer('global_average_pooling2d_1').output[..., orig_label])
        loss2 = K.mean(model2.get_layer('global_average_pooling2d_2').output[..., orig_label])
        loss3 = -args.weight_diff * K.mean(model3.get_layer('global_average_pooling2d_3').output[..., orig_label])

    # loss1_neuron = K.mean(model1.get_layer(layer_name1).output[..., index1])
    # loss2_neuron = K.mean(model2.get_layer(layer_name2).output[..., index2])
    # loss3_neuron = K.mean(model3.get_layer(layer_name3).output[..., index3])
    loss1_neuron = neuron_to_cover(model1, model_layer_dict1, args.neuron_to_cover_num)
    loss2_neuron = neuron_to_cover(model2, model_layer_dict2, args.neuron_to_cover_num)
    loss3_neuron = neuron_to_cover(model3, model_layer_dict3, args.neuron_to_cover_num)

    layer_output = (loss1 + loss2 + loss3) + args.weight_nc * (K.sum(loss1_neuron) + K.sum(loss2_neuron) + K.sum(loss3_neuron))

    # for adversarial image generation
    final_loss = K.mean(layer_output)

    # we compute the gradient of the input picture wrt this loss
    grads = normalize(K.gradients(final_loss, input_tensor)[0])

    grads = normalize(K.gradients(final_loss, input_tensor)[0])
    grads_tensor_list = [loss1, loss2, loss3]
    grads_tensor_list.extend(loss1_neuron)
    grads_tensor_list.extend(loss2_neuron)
    grads_tensor_list.extend(loss3_neuron)
    grads_tensor_list.append(grads)

    # this function returns the loss and grads given the input picture
    iterate = K.function([input_tensor], grads_tensor_list)

    print("Mutate the seed of number %d" % (i + 1))
    # we run gradient ascent for 20 steps
    for iters in range(args.grad_iterations):
        loss_neuron_list = iterate([gen_img])
        if args.transformation == 'light':
            grads_value = constraint_light(loss_neuron_list[-1])  # constraint the gradients value
        elif args.transformation == 'occl':
            grads_value = constraint_occl(loss_neuron_list[-1], args.start_point,
                                          args.occlusion_size)  # constraint the gradients value
        elif args.transformation == 'blackout':
            grads_value = constraint_black(loss_neuron_list[-1])  # constraint the gradients value

        gen_img += grads_value * args.step
        predictions1 = np.argmax(model1.predict(gen_img)[0])
        predictions2 = np.argmax(model2.predict(gen_img)[0])
        predictions3 = np.argmax(model3.predict(gen_img)[0])

        diff_img = gen_img - orig_img

        L2_norm = np.linalg.norm(diff_img)

        orig_L2_norm = np.linalg.norm(orig_img)

        perturb_adversial = L2_norm / orig_L2_norm

        if not predictions1 == predictions2 == predictions3:
            update_coverage(gen_img, model1, model_layer_dict1, args.threshold)
            update_coverage(gen_img, model2, model_layer_dict2, args.threshold)
            update_coverage(gen_img, model3, model_layer_dict3, args.threshold)

            total_norm += L2_norm
            total_perturb_adversial += perturb_adversial
            adversial_num += 1

            print(bcolors.OKGREEN + 'covered neurons percentage %d neurons %.3f, %d neurons %.3f, %d neurons %.3f'
                  % (len(model_layer_dict1), neuron_covered(model_layer_dict1)[2], len(model_layer_dict2),
                     neuron_covered(model_layer_dict2)[2], len(model_layer_dict3),
                     neuron_covered(model_layer_dict3)[2]) + bcolors.ENDC)
            averaged_nc = (neuron_covered(model_layer_dict1)[0] + neuron_covered(model_layer_dict2)[0] +
                           neuron_covered(model_layer_dict3)[0]) / float(
                neuron_covered(model_layer_dict1)[1] + neuron_covered(model_layer_dict2)[1] +
                neuron_covered(model_layer_dict3)[
                    1])
            print(bcolors.OKGREEN + 'averaged covered neurons %.3f' % averaged_nc + bcolors.ENDC)

            gen_img_deprocessed = deprocess_image(gen_img)
            orig_img_deprocessed = deprocess_image(orig_img)

            # save the result to disk
            imsave('./generated_inputs/' + args.transformation + '_' + str(predictions1) + '_' + str(
                predictions2) + '_' + str(predictions3) + '.png',
                   gen_img_deprocessed)
            imsave('./generated_inputs/' + args.transformation + '_' + str(predictions1) + '_' + str(
                predictions2) + '_' + str(predictions3) + '_orig.png',
                   orig_img_deprocessed)

            break

    end_time = time.clock()

    duration = end_time - start_time

    total_time += duration

result_txt = './output/output.txt'
result = 'All covered neurons percentage ' + str(len(model_layer_dict1)) +\
          ' neurons ' + str(neuron_covered(model_layer_dict1)[2]) + ';' +  str(len(model_layer_dict2)) +\
          ' neurons ' + str(neuron_covered(model_layer_dict2)[2]) + ';' + str(len(model_layer_dict3)) +\
          ' neurons ' + str(neuron_covered(model_layer_dict3)[2]) + '\n'

print('iteration' + str(args.grad_iterations))
result += 'grad_iterations' +str(args.grad_iterations) +'\n'

print('total_time = ' + str(total_time))
result += 'total_time = ' + str(total_time) + '\n'

print('total_norm = ' + str(total_norm))
result += 'total_norm = ' + str(total_norm) + '\n'

print('average_norm = ' + str(total_norm / adversial_num))
result += 'average_norm = ' + str(total_norm / adversial_num) + '\n'

print('adversial num = ' + str(adversial_num))
result += 'adversial num = ' + str(adversial_num) + '\n'

print('average perb adversial = ' + str(total_perturb_adversial / adversial_num))
result += 'average perb adversial = ' + str(total_perturb_adversial / adversial_num) + '\n' + '\n'

with open(result_txt, 'a') as file:
    file.write(result)
