import pydicom
import os
from copy import deepcopy
import numpy as np
import matplotlib.pyplot as plt
import csv
import stat
import math
from scipy.ndimage import zoom, gaussian_filter
import datetime
from lrfc_test import lrfc

def define_encoder_dict(unit=2):
    #this function initializes the dictionary of jaw positions --> encoder values. 
    #it reads an encoder csv file and stores the encoder values in a dictionary with their approximate (machine - read) symmetric jaw value
    encoder_file = os.path.join(os.getcwd(), "encoder_spreadsheets", f"u{unit}_encoders.csv")
    with open(encoder_file) as fp:
        reader = csv.reader(fp)
        csv_data_list = []
        for row in reader:
            csv_data_list.append(row)
    dic = {"x1": {}, "x2": {}, "y1": {}, "y2": {}}
    for row in csv_data_list[2:]:
        dic["x1"][round(float(row[0]),1)] = {"encoder": int(row[1]), "pixel": -100}
        dic["x2"][round(float(row[0]),1)] = {"encoder": int(row[2]), "pixel": -100}
        dic["y1"][round(float(row[0]),1)] = {"encoder": int(row[3]), "pixel": -100}
        dic["y2"][round(float(row[0]),1)] = {"encoder": int(row[4]), "pixel": -100}
    
    return dic

def round_to_point_five(x):
    #rounds value to nearest 0.5
    return round(round(2*x)/2,1)
def normalize_by_top_median(img, num=10000):
    #this function normalizes an image by the median of the top num of pixels
    flattened = deepcopy(img).flatten()
    sorted_pixels = np.sort(flattened)[::-1]
    hottest = sorted_pixels[:num]
    med=np.median(hottest)
    return  img / med

def fit_encoder_vs_pixel_funcs(img_folder, iso_img_path, unit_num, optimal_cal):
    #this function finds the epid pixels corresponding to each jaw position in img_dict, and then fits a curve to those pixel values with the jaw encoder readouts

    encoder_dic = define_encoder_dict(unit_num)   #initialize dictionary which will hold jaw positions, encoders, pixels
    #get iso img
    img_meta = pydicom.dcmread(iso_img_path)
    img = img_meta.pixel_array
    img = normalize_by_top_median(img)   #normalize image
    img = gaussian_filter(img, sigma=3, order=0)    #smoothen the image
    iso_img = zoom(img, zoom=2, order=3)
    iso = find_bead_location(iso_img, round_final=True)    #first get the pixel position of the isocentre

    for img_path in sorted(os.listdir(img_folder)):
        img_path = os.path.join(img_folder, img_path)
        img_meta = pydicom.dcmread(img_path)
        jaws_x = img_meta[0x3002,0x0030][0][0x300A,0x00B6][0][0x300A,0X011C].value
        jaws_y = img_meta[0x3002,0x0030][0][0x300A,0x00B6][1][0x300A,0X011C].value
        img = img_meta.pixel_array
        img = normalize_by_top_median(img)
        img = gaussian_filter(img, sigma=3, order=0)    #smoothen the image
        img = zoom(img, zoom=2, order=3)

        #x1:
        x1_profile = deepcopy(img[iso[0], 0:1500])
        #determine centre as pixel with sharpest gradient
        x1_profile_grad = np.gradient(x1_profile)
        x1_pixel_old = np.argmax(x1_profile_grad)
        x1_profile[:x1_pixel_old-20] = 1    #only find the right jaw by zoning in on correct gradient area
        x1_profile[x1_pixel_old+20:] = 1    #only find the right jaw by zoning in on correct gradient area
        x1_pixel = np.argmin(abs(x1_profile - 0.5))
        x1_displacement = round_to_point_five(round(abs(2*jaws_x[0])/10,1))#round((round(-4*(x1_pixel - iso[1]) * pixel_distance/2)/2),1)  #--> cm bc make negative to follow sign convention (positive if jaw crosses iso, negative if shy)     

        encoder_dic["x1"][x1_displacement]["pixel"] = x1_pixel

        #x2:
        x2_profile = deepcopy(img[iso[0], 1000:-1])

        #determine centre as pixel with sharpest gradient
        x2_profile_grad = np.gradient(x2_profile)
        x2_pixel_old = np.argmin(x2_profile_grad)
        x2_profile[:x2_pixel_old-20] = 1    #only find the right jaw by zoning in on correct gradient area
        x2_profile[x2_pixel_old+20:] = 1    #only find the right jaw by zoning in on correct gradient area
        x2_pixel = np.argmin(abs(x2_profile - 0.5))+1000
        x2_displacement = round_to_point_five(round(2*abs(jaws_x[1])/10,1))#round((round(4*(x2_pixel - iso[1]) * pixel_distance/2)/2),1)   #--> cm bc make negative to follow sign convention (positive if jaw crosses iso, negative if shy)     

        encoder_dic["x2"][x2_displacement]["pixel"] = x2_pixel


        #y1:
        y1_profile = deepcopy(img[1000:-1, iso[1]])

        #determine centre as pixel with sharpest gradient
        y1_profile_grad = np.gradient(y1_profile)
        y1_pixel_old = np.argmin(y1_profile_grad)
        y1_profile[:y1_pixel_old-20] = 1    #only find the right jaw by zoning in on correct gradient area
        y1_profile[y1_pixel_old+20:] = 1    #only find the right jaw by zoning in on correct gradient area
        y1_pixel = np.argmin(abs(y1_profile - 0.5))+1000
        y1_displacement = round_to_point_five(round(2*abs(jaws_y[0])/10,1))#round((round(4*(y1_pixel - iso[0]) * pixel_distance/2)/2),1)   #--> cm bc make negative to follow sign convention (positive if jaw crosses iso, negative if shy)     

        encoder_dic["y1"][y1_displacement]["pixel"] = y1_pixel

        #y2:
        y2_profile = deepcopy(img[0:1500, iso[1]])
        #determine centre as pixel with sharpest gradient
        y2_profile_grad = np.gradient(y2_profile)
        y2_pixel_old = np.argmax(y2_profile_grad)
        y2_profile[:y2_pixel_old-20] = 1    #only find the right jaw by zoning in on correct gradient area
        y2_profile[y2_pixel_old+20:] = 1    #only find the right jaw by zoning in on correct gradient area
        y2_pixel = np.argmin(abs(y2_profile - 0.5))
        y2_displacement = round_to_point_five(round(2*abs(jaws_y[1])/10,1))#round((round(-4*(y2_pixel - iso[0]) * pixel_distance/2)/2),1)   #--> cm bc make negative to follow sign convention (positive if jaw crosses iso, negative if shy)     
        
        encoder_dic["y2"][y2_displacement]["pixel"] = y2_pixel


    
    #now want to fit cubic functions of each jaws pixel vs encoder value. 
    fig, ax = plt.subplots(nrows=4, ncols=1)
    for j, jaw in enumerate(["x1", "x2", "y1", "y2"]):
        encoders = []
        pixels = []
        for val in encoder_dic[jaw].keys():
            
            if encoder_dic[jaw][val]["pixel"] == -100:   #if still at default value, image wasn't found at this position
                continue
            encoders.append(encoder_dic[jaw][val]["encoder"])
            pixels.append(encoder_dic[jaw][val]["pixel"])

        encoders = np.array(encoders)
        pixels = np.array(pixels)

        #now want a cubic fit to the data:
        fit = np.polyfit(pixels,encoders,deg=3)
        print(f"Polynomial fit coefficients: {fit}")

        #plot:
        pixels_fit = np.linspace(np.amin(pixels), np.amax(pixels),200)
        fit_points = fit[0]*pixels_fit**3 + fit[1]*pixels_fit**2 + fit[2]*pixels_fit + fit[3]

        ax[j].scatter(pixels, encoders, c="salmon")
        ax[j].plot(pixels_fit, fit_points, marker=None, c="mediumturquoise")
        ax[j].set_xlabel("EPID Pixel")
        ax[j].set_ylabel(f"{jaw} Jaw Encoder Value")

        #also get the predicted location of the locations 1,5,9,19 using the optimal calibration point as the origin
        iso = find_bead_location(iso_img, round_final=False) #get unrounded iso
        p1, p5, p9, p19 = predict_opt_cal_locations(iso, jaw, optimal_cal, fit)
        if j == 0:
            ax[j].text(100, np.mean(encoders), f"p1: {p1}, p5: {p5}, p9: {p9}, p19: {p19}")
        if j == 1:
            ax[j].text(1300, np.mean(encoders),f"p1: {p1}, p5: {p5}, p9: {p9}, p19: {p19}")
        if j == 2:
            ax[j].text(1300,  np.mean(encoders), f"p1: {p1}, p5: {p5}, p9: {p9}, p19: {p19}")
        if j == 3:
            ax[j].text(100,  np.mean(encoders), f"p1: {p1}, p5: {p5}, p9: {p9}, p19: {p19}")
    fig.savefig(os.path.join(os.getcwd(), f"U{unit_num}_Output", f"encoder_plots_cubic"))


    #now fit a linear curve
    fig, ax = plt.subplots(nrows=4, ncols=1)
    for j, jaw in enumerate(["x1", "x2", "y1", "y2"]):
        encoders = []
        pixels = []
        for val in encoder_dic[jaw].keys():
            
            if encoder_dic[jaw][val]["pixel"] == -100:   #if still at default value, image wasn't found at this position
                continue
            encoders.append(encoder_dic[jaw][val]["encoder"])
            pixels.append(encoder_dic[jaw][val]["pixel"])

        encoders = np.array(encoders)
        pixels = np.array(pixels)

        #now want a cubic fit to the data:
        fit = np.polyfit(pixels,encoders,deg=1)
        print(f"Polynomial fit coefficients: {fit}")

        #plot:
        pixels_fit = np.linspace(np.amin(pixels), np.amax(pixels),200)
        fit_points = fit[0]*pixels_fit + fit[1]

        ax[j].scatter(pixels, encoders, c="salmon")
        ax[j].plot(pixels_fit, fit_points, marker=None, c="mediumturquoise")
        ax[j].set_xlabel("EPID Pixel")
        ax[j].set_ylabel(f"{jaw} Jaw Encoder Value")

        #also get the predicted location of the locations 1,5,9,19 using the optimal calibration point as the origin
        iso = find_bead_location(iso_img, round_final=False) #get unrounded iso
        p1, p5, p9, p19 = predict_opt_cal_locations(iso, jaw, optimal_cal, fit)
        if j == 0:
            ax[j].text(100, np.mean(encoders), f"p1: {p1}, p5: {p5}, p9: {p9}, p19: {p19}")
        if j == 1:
            ax[j].text(1300, np.mean(encoders),f"p1: {p1}, p5: {p5}, p9: {p9}, p19: {p19}")
        if j == 2:
            ax[j].text(1300,  np.mean(encoders), f"p1: {p1}, p5: {p5}, p9: {p9}, p19: {p19}")
        if j == 3:
            ax[j].text(100,  np.mean(encoders), f"p1: {p1}, p5: {p5}, p9: {p9}, p19: {p19}")
    fig.savefig(os.path.join(os.getcwd(), f"U{unit_num}_Output", f"encoder_plots_linear"))
    
        
    return

def predict_opt_cal_locations(iso, jaw, optimal_cal, fit, epid_position=1.18):
    pixel_distance = 0.336 / epid_position / 2
    #this function returns the encoder values of the jaw calibration positions (1,5,9,19) calculated relative to optimal origin

    #first get the jaw positions in pixels, relative to origin.
    if jaw == "x1":
        origin = iso[1] - optimal_cal[0]/(pixel_distance)   #optimal_cal in millimetres
        p1 = origin - (10/pixel_distance)
        p5 = origin - 50*(1/pixel_distance)
        p9 = origin - 90*(1/pixel_distance)
        p19 = origin - 190*(1/pixel_distance)
    if jaw == "x2":
        origin = iso[1] + optimal_cal[1]/(pixel_distance) 
        p1 = origin + (10/pixel_distance)
        p5 = origin + 50*(1/pixel_distance)
        p9 = origin + 90*(1/pixel_distance)
        p19 = origin + 190*(1/pixel_distance)
    if jaw == "y1":
        origin = iso[0] + optimal_cal[2]/(pixel_distance) 
        p1 = origin + (10/pixel_distance)
        p5 = origin + 50*(1/pixel_distance)
        p9 = origin + 90*(1/pixel_distance)
        p19 = origin + 190*(1/pixel_distance)
    if jaw == "y2":
        origin = iso[0] - optimal_cal[3]/(pixel_distance) 
        p1 = origin - (10/pixel_distance)
        p5 = origin - 50*(1/pixel_distance)
        p9 = origin - 90*(1/pixel_distance)
        p19 = origin - 190*(1/pixel_distance)
    if len(fit) == 4:
        p1 = fit[0]*p1**3 + fit[1]*p1**2 + fit[2]*p1 + fit[3]
        p5 = fit[0]*p5**3 + fit[1]*p5**2 + fit[2]*p5 + fit[3]
        p9 = fit[0]*p9**3 + fit[1]*p9**2 + fit[2]*p9 + fit[3]
        p19 = fit[0]*p19**3 + fit[1]*p19**2 + fit[2]*p19 + fit[3]
    elif len(fit) == 2:
        p1 = fit[0]*p1 + fit[1]
        p5 = fit[0]*p5 + fit[1]
        p9 = fit[0]*p9 + fit[1]
        p19 = fit[0]*p19 + fit[1]

    return [round(p1), round(p5), round(p9), round(p19)]

def sort_junc_img_dict(img_folder : str):
    #first load images into a dictionary based on gantry angle and collimator angle
    imgs = {}    #initiate the image dictionary

    #go through the image directory and sort and store images
    for img_path in os.listdir(img_folder):
        img_path = os.path.join(img_folder, img_path)
        img_meta = pydicom.dcmread(img_path)
        jaws_x = img_meta[0x3002,0x0030][0][0x300A,0x00B6][0][0x300A,0X011C].value
        jaws_y = img_meta[0x3002,0x0030][0][0x300A,0x00B6][1][0x300A,0X011C].value
        img = img_meta.pixel_array
        img = normalize_by_top_median(img)
        img = gaussian_filter(img, sigma=3, order=0)    #smoothen the image
        img = zoom(img, zoom=2, order=3)
        # jaws = img_meta[0x3002,0x0030].value[0][0x300A, 0x00B6][0]
        
        gantry_angle = round(float(img_meta[0x300A,0x011E].value)) % 360

        if gantry_angle not in imgs.keys():
            imgs[gantry_angle] = {}

        coll_angle = round(float(img_meta[0x300A, 0x0120].value)) % 360
        if coll_angle not in imgs[gantry_angle].keys():
            imgs[gantry_angle][coll_angle] = {}

        imager_location = round(float(img_meta[0x3002, 0x000D].value[2]))    #get location of EPID receptor panel

        #old method (when position 0 was used for other images)
        #
        #
        #if epid location is at -500, image is of the cube phantom with the bb to demark isocentre
        # if imager_location == -500:
        #     imgs[gantry_angle]["iso"] = img   #using same image for both coll rotations... isocentre defined by bb over epid
        #     continue
        #
        #
        
        #collimator positions not included in metadata, so determine closed jaw from lowest mean pixel intensity in each quarter blocked region
        y_range, x_range = img.shape
        #order of quarter regions is: [left, right, top, bottom]
        mean_blocked_pixels = [np.mean(img[:, :int(x_range/2)]), np.mean(img[:, int(x_range/2):]), np.mean(img[:int(x_range/2), :]), np.mean(img[int(x_range/2):, :])]    #C0: x1, x2, y2, y1 / C90: y2, y1, x2, x1 
        
        min_region_index = np.argmin(mean_blocked_pixels)
        
        #if field is symmetric, then it is the isocentre image (no closed jaws)
        if (np.amin(mean_blocked_pixels)/np.amax(mean_blocked_pixels)) > 0.6: 
            imgs[gantry_angle]["iso"] = img
            #find_bead_location(img)
            continue

        blocked_field = ""

        if coll_angle == 0:
            if min_region_index == 0:
                blocked_field = "x1"
            if min_region_index == 1:
                blocked_field = "x2"
            if min_region_index == 2:
                blocked_field = "y2"
            if min_region_index == 3:
                blocked_field = "y1"
        elif coll_angle == 90:
            if min_region_index == 0:
                blocked_field = "y2"
            if min_region_index == 1:
                blocked_field = "y1"
            if min_region_index == 2:
                blocked_field = "x2"
            if min_region_index == 3:
                blocked_field = "x1"

        elif coll_angle == 270:
            if min_region_index == 0:
                blocked_field = "y1"
            if min_region_index == 1:
                blocked_field = "y2"
            if min_region_index == 2:
                blocked_field = "x1"
            if min_region_index == 3:
                blocked_field = "x2"



        imgs[gantry_angle][coll_angle][blocked_field] = img

    return imgs

def sort_jaw_img_dict(img_folder : str):

    imgs = {}    #initiate the image dictionary
    imgs["x1"] = {}
    imgs["x2"] = {}
    imgs["y1"] = {}
    imgs["y2"] = {}


    #go through the image directory and sort and store images
    for img_path in os.listdir(img_folder):
        img_path = os.path.join(img_folder, img_path)
        img_meta = pydicom.dcmread(img_path)
        jaws_x = img_meta[0x3002,0x0030][0][0x300A,0x00B6][0][0x300A,0X011C].value
        jaws_y = img_meta[0x3002,0x0030][0][0x300A,0x00B6][1][0x300A,0X011C].value
        img = img_meta.pixel_array
        img = normalize_by_top_median(img)
        img = gaussian_filter(img, sigma=3, order=0)    #smoothen the image
        img = zoom(img, zoom=2, order=3)
         
        #collimator positions not included in metadata, so determine closed jaw from lowest mean pixel intensity in each quarter blocked region
        y_range, x_range = img.shape
        #order of quarter regions is: [left, right, top, bottom]
        # mean_blocked_pixels = [np.mean(img[:, :int(x_range/2)]), np.mean(img[:, int(x_range/2):]), np.mean(img[:int(x_range/2), :]), np.mean(img[int(x_range/2):, :])]    #C0: x1, x2, y2, y1 / C90: y2, y1, x2, x1 
        # min_region_index = np.argmin(mean_blocked_pixels)

        # if min_region_index == 0:
        #     blocked_field = abs("x1")
        #     nominal_jaw = jaws_x[0]

        # if min_region_index == 1:
        #     blocked_field = "x2"
        #     nominal_jaw = abs(jaws_x[1])

        # if min_region_index == 2:
        #     blocked_field = "y2"
        #     nominal_jaw = abs(jaws_y[1])

        # if min_region_index == 3:
        #     blocked_field = "y1"
        #     nominal_jaw = abs(jaws_y[0])
        blocked_field = "x1"
        nominal_jaw = abs(jaws_x[0])
        imgs[blocked_field][round(nominal_jaw/10, 1)] = img

        blocked_field = "x2"
        nominal_jaw = abs(jaws_x[1])
        imgs[blocked_field][round(nominal_jaw/10, 1)] = img

        blocked_field = "y2"
        nominal_jaw = abs(jaws_y[1])
        imgs[blocked_field][round(nominal_jaw/10, 1)] = img

        blocked_field = "y1"
        nominal_jaw = abs(jaws_y[0])
        imgs[blocked_field][round(nominal_jaw/10, 1)] = img

    return imgs

def get_junc_offsets(img_dict, unit_num):
    #this function will determine the offset of each 1/4 blocked beam jaw with the isocentre (defined by bead in each phantom image at each gantry/coll setting)
    #values will be reported such that negative means the jaw passed over the iso, positive means it doesn't reach it. 
    
    #start by defining a dictionary of same format as img_dict that will hold the offsets.
    offset_dict = deepcopy(img_dict)

    
    for g in img_dict.keys():    #go through all gantry angles

        image = img_dict[g]["iso"]
        #start by getting the isocentre bead pixel location for each setting
        offset_dict[g]["iso"] = find_bead_location(image, round_final=False)
        
        #start with c = 0 images
        isocentre = offset_dict[g]["iso"]

        #y1 - want profile through centre y along x
        y1_profile = deepcopy(img_dict[g][0]["y1"][:, round(isocentre[1])])
        y1_profile[0:int(y1_profile.size/4)] = 1    #make borders zero so that center closed jaw is properly found, and not the other jaw edge. 
        y1_profile[int(3*y1_profile.size/4):] = 1
        # plt.plot(y1_profile)
        # plt.show()
        #determine centre as pixel with sharpest gradient

        y1_offset = (np.argmin(abs(y1_profile - 0.5)) - isocentre[0]) * 0.224/2   #make negative to follow sign convention (positive if jaw openy)     
        offset_dict[g][0]["y1"] = y1_offset 

        #repeat for y2 jaw
        y2_profile = deepcopy(img_dict[g][0]["y2"][:, round(isocentre[1])])
        y2_profile[0:int(y2_profile.size/4)] = 1    #make borders zero so that center closed jaw is properly found, and not the other jaw edge. 
        y2_profile[int(3*y2_profile.size/4):] = 1
        # plt.plot(y2_profile)
        # plt.show()

        y2_offset = -(np.argmin(abs(y2_profile - 0.5)) - isocentre[0])* 0.224/2
        offset_dict[g][0]["y2"] = y2_offset 

        #repeat for x1 jaw
        x1_profile = deepcopy(img_dict[g][0]["x1"][round(isocentre[0]), :])
        x1_profile[0:int(x1_profile.size/4)] = 1    #make borders zero so that center closed jaw is properly found, and not the other jaw edge. 
        x1_profile[int(3*x1_profile.size/4):] = 1
        # plt.plot(x1_profile)
        # plt.show()

        x1_offset = -(np.argmin(abs(x1_profile - 0.5)) - isocentre[1])* 0.224/2
        offset_dict[g][0]["x1"] = x1_offset  

        #repeat for x2 jaw
        x2_profile = deepcopy(img_dict[g][0]["x2"][round(isocentre[0]), :])
        x2_profile[0:int(x2_profile.size/4)] = 1    #make borders zero so that center closed jaw is properly found, and not the other jaw edge. 
        x2_profile[int(3*x2_profile.size/4):] = 1
        # plt.plot(x2_profile)
        # plt.show()

        x2_offset = (np.argmin(abs(x2_profile - 0.5)) - isocentre[1])* 0.224/2
        offset_dict[g][0]["x2"] = x2_offset 


        # fig, ax = plt.subplots(nrows=4, ncols=3, figsize=(17, 17))
        # ax[0,0].set_title(f"Gantry Angle: {g}$^\circ$, Collimator Angle: {0}$^\circ$")
        # ax[0,0].plot(y1_profile)
        # ax[0,1].plot(y1_profile_grad)
        # ax[0,2].imshow(img_dict[g][0]["y1"])
        # ax[0,0].text(1450, 0.8, f"Y1 Jaw offset = {round(y1_offset,3)} mm")    #pixel size 0.34 mm /2
    
        # ax[1,0].plot(y2_profile)
        # ax[1,1].plot(y2_profile_grad)
        # ax[1,2].imshow(img_dict[g][0]["y2"])
        # ax[1,0].text(0, 0.8, f"Y2 Jaw offset = {round(y2_offset,3)} mm")    #pixel size 0.34 mm /2

        # ax[2,0].plot(x1_profile)
        # ax[2,1].plot(x1_profile_grad)
        # ax[2,2].imshow(img_dict[g][0]["x1"])
        # ax[2,0].text(0, 0.8, f"X1 Jaw offset = {round(x1_offset,3)} mm")    #pixel size 0.34 mm /2

        # ax[3,0].plot(x2_profile)
        # ax[3,1].plot(x2_profile_grad)
        # ax[3,2].imshow(img_dict[g][0]["x2"])
        # ax[3,0].text(1450, 0.8, f"X2 Jaw offset = {round(x2_offset,3)} mm")    #pixel size 0.34 mm /2

        #fig.savefig(os.path.join(os.getcwd(), f"U{unit_num}_Output", f"{g}_{0}_{datetime.datetime.now().strftime("%Y-%m-%d_%H_%M_%S")}"))
        #plt.show()
        #del fig

        #plt.close()

  

        #y1 - want profile through centre y along x
        x1_profile = deepcopy(img_dict[g][90]["x1"][:, round(isocentre[1])])
        x1_profile[0:int(x1_profile.size/4)] = 1    #make borders zero so that center closed jaw is properly found, and not the other jaw edge. 
        x1_profile[int(3*x1_profile.size/4):] = 1
        #determine centre as pixel with sharpest gradient
        x1_profile_grad = np.gradient(x1_profile)
        x1_offset = (np.argmin(abs(x1_profile - 0.5)) - isocentre[0])* 0.224/2   #make negative to follow sign convention (positive if jaw crosses iso, negative if shy)
        offset_dict[g][90]["x1"] = x1_offset

        #repeat for y2 jaw
        x2_profile = deepcopy(img_dict[g][90]["x2"][:, round(isocentre[1])])
        x2_profile[0:int(x2_profile.size/4)] = 1    #make borders zero so that center closed jaw is properly found, and not the other jaw edge. 
        x2_profile[int(3*x2_profile.size/4):] = 1
        x2_profile_grad = np.gradient(x2_profile)
        x2_offset = -(np.argmin(abs(x2_profile - 0.5)) - isocentre[0])* 0.224/2
        offset_dict[g][90]["x2"] = x2_offset 

        #repeat for x1 jaw
        y2_profile = deepcopy(img_dict[g][90]["y2"][round(isocentre[0]), :])
        y2_profile[0:int(y2_profile.size/4)] = 1    #make borders zero so that center closed jaw is properly found, and not the other jaw edge. 
        y2_profile[int(3*y2_profile.size/4):] = 1
        y2_profile_grad = np.gradient(y2_profile)
        y2_offset = -(np.argmin(abs(y2_profile - 0.5)) - isocentre[1])* 0.224/2
        offset_dict[g][90]["y2"] = y2_offset

        #repeat for x2 jaw
        y1_profile = deepcopy(img_dict[g][90]["y1"][round(isocentre[0]), :])
        y1_profile[0:int(y1_profile.size/4)] = 1    #make borders zero so that center closed jaw is properly found, and not the other jaw edge. 
        y1_profile[int(3*y1_profile.size/4):] = 1
        y1_profile_grad = np.gradient(y1_profile)
        y1_offset = (np.argmin(abs(y1_profile - 0.5)) - isocentre[1])* 0.224/2
        offset_dict[g][90]["y1"] = y1_offset 


        # fig, ax = plt.subplots(nrows=4, ncols=3, figsize=(17,17))
        
        # ax[0,0].set_title(f"Gantry Angle: {g}$^\circ$, Collimator Angle: {90}$^\circ$")
        # ax[0,0].plot(y1_profile)
        # ax[0,1].plot(y1_profile_grad)
        # ax[0,2].imshow(img_dict[g][90]["y1"])
        # ax[0,0].text(1450, 0.8, f"Y1 Jaw offset = {round(y1_offset,3)} mm")    #pixel size 0.34 mm /2
    
        # ax[1,0].plot(y2_profile)
        # ax[1,1].plot(y2_profile_grad)
        # ax[1,2].imshow(img_dict[g][90]["y2"])
        # ax[1,0].text(0, 0.8, f"Y2 Jaw offset = {round(y2_offset,3)} mm")    #pixel size 0.34 mm /2

        # ax[2,0].plot(x1_profile)
        # ax[2,1].plot(x1_profile_grad)
        # ax[2,2].imshow(img_dict[g][90]["x1"])
        # ax[2,0].text(1450, 0.8, f"X1 Jaw offset = {round(x1_offset,3)} mm")    #pixel size 0.34 mm /2

        # ax[3,0].plot(x2_profile)
        # ax[3,1].plot(x2_profile_grad)
        # ax[3,2].imshow(img_dict[g][90]["x2"])
        # ax[3,0].text(0, 0.8, f"X2 Jaw offset = {round(x2_offset,3)} mm")    #pixel size 0.34 mm /2
        
        # fig.savefig(os.path.join(os.getcwd(), f"U{unit_num}_Output", f"{g}_{90}_{datetime.datetime.now().strftime("%Y-%m-%d_%H_%M_%S")}"))
        # del fig
        # plt.close()
        #plt.show()


        #Now repeat for the c = 270 images from left counter clockwise - (y1, x2, y2, x1)
        #x2 - want profile through centre y along x
        x2_profile = deepcopy(img_dict[g][270]["x2"][:, round(isocentre[1])])
        x2_profile[0:int(x2_profile.size/4)] = 1    #make borders zero so that center closed jaw is properly found, and not the other jaw edge. 
        x2_profile[int(3*x2_profile.size/4):] = 1
        #determine centre as pixel with sharpest gradient
        x2_profile_grad = np.gradient(x2_profile)
        x2_offset = (np.argmin(abs(x2_profile - 0.5)) - isocentre[0]) * 0.224/2   #make negative to follow sign convention (positive if jaw crosses iso, negative if shy)     
        # plt.plot(x2_profile)
        # plt.show()
        offset_dict[g][270]["x2"] = x2_offset 

        #repeat for x1 jaw
        x1_profile = deepcopy(img_dict[g][270]["x1"][:, round(isocentre[1])])
        x1_profile[0:int(x1_profile.size/4)] = 1    #make borders zero so that center closed jaw is properly found, and not the other jaw edge. 
        x1_profile[int(3*x1_profile.size/4):] = 1
        x1_profile_grad = np.gradient(x1_profile)
        x1_offset = -(np.argmin(abs(x1_profile - 0.5)) - isocentre[0])* 0.224/2
        offset_dict[g][270]["x1"] = x1_offset 

        #repeat for y1 jaw
        y1_profile = deepcopy(img_dict[g][270]["y1"][round(isocentre[0]), :])
        y1_profile[0:int(y1_profile.size/4)] = 1    #make borders zero so that center closed jaw is properly found, and not the other jaw edge. 
        y1_profile[int(3*y1_profile.size/4):] = 1
        y1_profile_grad = np.gradient(y1_profile)
        y1_offset = -(np.argmin(abs(y1_profile - 0.5)) - isocentre[1])* 0.224/2
        offset_dict[g][270]["y1"] = y1_offset  

        #repeat for y2 jaw
        y2_profile = deepcopy(img_dict[g][270]["y2"][round(isocentre[0]), :])
        y2_profile[0:int(y2_profile.size/4)] = 1    #make borders zero so that center closed jaw is properly found, and not the other jaw edge. 
        y2_profile[int(3*y2_profile.size/4):] = 1
        y2_profile_grad = np.gradient(y2_profile)
        y2_offset = (np.argmin(abs(y2_profile - 0.5)) - isocentre[1])* 0.224/2
        offset_dict[g][270]["y2"] = y2_offset 


        # fig, ax = plt.subplots(nrows=4, ncols=3, figsize=(17, 17))
        # ax[0,0].set_title(f"Gantry Angle: {g}$^\circ$, Collimator Angle: {270}$^\circ$")
        # ax[0,0].plot(y1_profile)
        # ax[0,1].plot(y1_profile_grad)
        # ax[0,2].imshow(img_dict[g][270]["y1"])
        # ax[0,0].text(1450, 0.8, f"Y1 Jaw offset = {round(y1_offset,3)} mm")    #pixel size 0.34 mm /2
    
        # ax[1,0].plot(y2_profile)
        # ax[1,1].plot(y2_profile_grad)
        # ax[1,2].imshow(img_dict[g][270]["y2"])
        # ax[1,0].text(0, 0.8, f"Y2 Jaw offset = {round(y2_offset,3)} mm")    #pixel size 0.34 mm /2

        # ax[2,0].plot(x1_profile)
        # ax[2,1].plot(x1_profile_grad)
        # ax[2,2].imshow(img_dict[g][270]["x1"])
        # ax[2,0].text(0, 0.8, f"X1 Jaw offset = {round(x1_offset,3)} mm")    #pixel size 0.34 mm /2

        # ax[3,0].plot(x2_profile)
        # ax[3,1].plot(x2_profile_grad)
        # ax[3,2].imshow(img_dict[g][270]["x2"])
        # ax[3,0].text(1450, 0.8, f"X2 Jaw offset = {round(x2_offset,3)} mm")    #pixel size 0.34 mm /2

        # fig.savefig(os.path.join(os.getcwd(), f"U{unit_num}_Output", f"{g}_{0}_{datetime.datetime.now().strftime("%Y-%m-%d_%H_%M_%S")}"))
        # #plt.show()
        # del fig
        # plt.close()

    #now want bar plots of offsets vs/ gantry / collimator for each angle
    #for clustered bar, need to sort data first into a new dictionary for plotting

    for jaw in ["x1", "x2", "y1", "y2"]:
        gantry_angles = sorted(offset_dict.keys())
        plot_dic = {}
        for c in [90, 0, 270]:
            vals = []
            for g in sorted(offset_dict.keys()):
                vals.append(offset_dict[g][c][jaw])
            plot_dic[c] = tuple(vals)
        
        g_range = np.arange(len(offset_dict.keys()))
        width = 0.25
        multiplier = 0

        fig, ax = plt.subplots(layout='constrained')
        colors= ["salmon", "moccasin", "skyblue"]    #colours for diff coll angles
        for c, val in plot_dic.items():
            offset = width * multiplier
            rects = ax.bar(g_range + offset, val, width, label=f"Collimator {c}$^\circ$", color=colors[multiplier], edgecolor="black")
            ax.bar_label(rects, padding=3, rotation=90)
            multiplier += 1
        ax.set_ylabel("Offset from isocentre (mm)")
        ax.set_title(f"{jaw.upper()} Jaw Offset From Isocentre")
        ax.set_xticks(g_range + width, gantry_angles)
        ylims = ax.get_ylim()
        ax.set_ylim([ylims[0]-abs(ylims[0])*0.15, ylims[1]+abs(ylims[1])*0.15])
        #reset axes to fit legend nicely
        box = ax.get_position()
        ax.set_position([box.x0, box.y0+box.height * 0.1, box.width, box.height * 0.9])
        ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.05), fancybox=True, shadow=True, ncol=3)
        fig.savefig(os.path.join(os.getcwd(), f"U{unit_num}_Output", f"bar_plot_offsets_{jaw}_{datetime.datetime.now().strftime("%Y-%m-%d_%H_%M_%S")}"))
        # plt.show(block=True)
        # plt.close()
        # plt.cla()
        del fig
            



    return offset_dict
            
def get_jaw_offsets(img_dict,isocentre):
    #this function will determine the offset of each 1/4 blocked beam jaw with the isocentre (defined by bead in each phantom image at each gantry/coll setting)
    #values will be reported such that negative means the jaw passed over the iso, positive means it doesn't reach it. 
    
    #start by defining a dictionary of same format as img_dict that will hold the offsets.
    offset_dict = {"y1": {}, "y2": {}, "x1": {}, "x2": {}}

    for fs in [2.5, 5.0,7.5, 10.0]:
        #y1 - want profile through centre y along x
        try:
            y1_profile = deepcopy(img_dict["y1"][fs][:, round(isocentre[1])])
            y1_profile[0:int(y1_profile.size/2)] = 1  
            y1_offset = (np.argmin(abs(y1_profile - 0.5)) - isocentre[0]) * 0.224/2   #make negative to follow sign convention (positive if jaw openy)     
            offset_dict["y1"][fs] = round(y1_offset /10, 2)
        except:
            print(f"Could not find asymmetric jaw image for Y1 and fs: {fs}")

        #repeat for y2 jaw
        try:
            y2_profile = deepcopy(img_dict["y2"][fs][:, round(isocentre[1])])
            y2_profile[int(y2_profile.size/2):] = 1  
            y2_offset = -(np.argmin(abs(y2_profile - 0.5)) - isocentre[0])* 0.224/2
            offset_dict["y2"][fs] = round(y2_offset/10, 2)
        except:
            print(f"Could not find asymmetric jaw image for Y2 and fs: {fs}")

        #repeat for x1 jaw
        try:
            x1_profile = deepcopy(img_dict["x1"][fs][round(isocentre[0]), :])
            x1_profile[int(x1_profile.size/2):] = 1  
            x1_offset = -(np.argmin(abs(x1_profile - 0.5)) - isocentre[1])* 0.224/2
            offset_dict["x1"][fs] = round(x1_offset/10, 2)
        except:
            print(f"Could not find asymmetric jaw image for X1 and fs: {fs}")

        #repeat for x2 jaw
        try:
            x2_profile = deepcopy(img_dict["x2"][fs][round(isocentre[0]), :])
            x2_profile[0:int(x2_profile.size/2)] = 1    #make borders zero so that center closed jaw is properly found, and not the other jaw edge. 
            x2_offset = (np.argmin(abs(x2_profile - 0.5)) - isocentre[1])* 0.224/2
            offset_dict["x2"][fs] = round(x2_offset/10, 2)
        except:
            print(f"Could not find asymmetric jaw image for Y2 and fs: {fs}")

    return offset_dict

def find_bead_location(image: np.array, round_final=True):
    #here we simply determine the pixel location of the centre of the bead in the cubic phantom
    #img = (deepcopy(image) - np.amin(image)) / (np.amax(image) - np.amin(image))
    img = deepcopy(image) / np.amax(image)
    # plt.imshow(img)
    # plt.show()

    #make outside borders large to make isocentre lowest value
    img[:,0:int(14*img.shape[1]/30)] = 1
    img[:,int(16*img.shape[1]/30):] = 1
    img[0:int(14*img.shape[0]/30),:] = 1
    img[int(16*img.shape[0]/30):,:] = 1


    #now keep the lowest 100 pixels (will be the bead location, and find centre of mass)
    pixel_list = sorted(img.flatten().tolist())
    pixel_100 = pixel_list[200]
    img[img > pixel_100] = 0

    # plt.imshow(img)
    # plt.show()

    #now find the centre of mass of the remaining pixels 
    centre_pixels = np.nonzero(img)

    centre_of_mass = np.mean(centre_pixels, axis=1)

    img[round(centre_of_mass[0]), round(centre_of_mass[1])] = 1
    # plt.imshow(img)
    # plt.show()
    print(centre_of_mass)

    if round_final==False:
        return [round(centre_of_mass[0], 2), round(centre_of_mass[1],2)]
    else:
        return [round(centre_of_mass[0]), round(centre_of_mass[1])]

def calculate_cost(offsets : dict, old_offsets, use_lrfc, lrfc_vals,junction_priority=0.5, optimize_lrfc=True, optimize_junctions=True):
    #this function takes a dictionary of jaw offsets at all gantry/collimator angles and returns the cost function
    #junction_priority (default 0.8) - the fraction of the total gap "cost function" that is given to sum of junction gaps/overlaps. 
    #
    # The remaining fraction (1-junction_priority) will go towards minimizing the absolute value of all jaw offsets at each angle.

    cost_absolute = 0    #this is the portion of the cost due to the absolute offsets (not related to junctions)

    #start by computing the sum of all jaw offsets at all gantry/collimator angles (absolute positions)
    for g in offsets.keys():
        # if g == 270:
        #     continue
        for c in offsets[g].keys():
            if c == "iso":
                continue
            for jaw in ["x1","x2", "y1", "y2"]:
                cost_absolute += abs(offsets[g][c][jaw])
    #normalize by number of total jaw images (4 * 3 * 8)
    cost_absolute /= (4*3*8)

    ##
    ##

    #now get the cost related to junctions (specifically interested in g0c90/g180c90 x1 w/ c90 x2 at all non 0/180 gantry angles)
    if optimize_junctions == True:
        cost_junction = 0
        #first get the supraclav field junctions
        g0c90_x1 = offsets[0][90]["x1"]
        g180c90_x1 = offsets[180][90]["x1"]


        #now get the lower field junctions
        for g in [50, 130, 310, 230]:
            lower_x2 = offsets[g][90]["x2"]
            junction_gap_0 = abs(lower_x2 + g0c90_x1)  #adding together will give the total error from perfect junction (whether it's a gap or an overlap)
            junction_gap_180 = abs(lower_x2 + g180c90_x1)

            cost_junction += junction_gap_0
            cost_junction += junction_gap_180
        #normalize junction cost by total number of relevant junctions (8)
        cost_junction /= 8

        ##
        ##
        #lastly, need extra cost for junctions that make field colder (rather yhsn hotter --> negative)
        cost_cold_junction = 0
        for g in [50, 130, 310, 230]:
            lower_x2 = offsets[g][90]["x2"]
            junction_gap_0 = lower_x2 + g0c90_x1  #adding together will give the total error from perfect junction (whether it's a gap or an overlap)
            junction_gap_180 = lower_x2 + g180c90_x1
            if junction_gap_0 < 0:
                cost_cold_junction += 0.5*abs(junction_gap_0)
            if junction_gap_180 < 0:
                cost_cold_junction += 0.5*abs(junction_gap_180)

        cost_cold_junction /= 8

        #now total cost is a combination of the three values (based on the junction priority)
        cost = junction_priority*(cost_junction+cost_cold_junction) + (1-junction_priority)*cost_absolute
    else:
        cost = cost_absolute


    #Want to add cost term based on the lrfc values if use_lrfc == True
    if use_lrfc == True:
        #want to calculate the new displacement of rad/light field.
        #first calculate how much each jaw is shifted from original configuration
        disp_x1 = offsets[0][0]["x1"] - old_offsets[0][0]["x1"]
        disp_x2 = offsets[0][0]["x2"] - old_offsets[0][0]["x2"]
        disp_y1 = offsets[0][0]["y1"] - old_offsets[0][0]["y1"]
        disp_y2 = offsets[0][0]["y2"] - old_offsets[0][0]["y2"]
        #now calculate new lrfc val for all lrfc images checked

        lrfc_cost = 0
        for lrfc_val in lrfc_vals:
            new_rad_light_y = lrfc_val[0] + (disp_y1/2 + -disp_y2/2) 
            new_rad_light_x = lrfc_val[1] + (-disp_x1/2 + disp_x2/2)

            if new_rad_light_y < 0.4: 
                if optimize_lrfc:
                    lrfc_cost += 0#abs(new_rad_light_y)
            elif new_rad_light_y < 0.9:
                lrfc_cost += abs(new_rad_light_y**2)
            else:
                lrfc_cost = abs(new_rad_light_y**3) #huge cost, do not want an lrfc value out of action

            if new_rad_light_x < 0.4: 
                if optimize_lrfc:
                    lrfc_cost += 0#abs(new_rad_light_x)
            elif new_rad_light_x < 0.9:
                lrfc_cost += abs(new_rad_light_x*2)
            else:
                lrfc_cost = abs(new_rad_light_x*3) #huge cost, do not want an lrfc value out of action

        lrfc_cost /= len(lrfc_vals)

        cost += lrfc_cost


    return cost


def get_opt_origin(offsets : dict, jaw_offsets, junction_priority, unit_num, lrfc_folder=None, optimize_junctions=True):
    #this function takes the offset dictionary (for each gantry angle, each collimator angle, each jaw) and computes the optimal calibration point.
    # our primary objective is to minimize the sum of gaps between g0c90, g180c90 - x2 and off axis gantry angles w/ collimator 90 and x1
    #
    #Variables:
    #offsets (dict)
    #junction_priority (default 0.8) - the fraction of the total gap "cost function" that is given to sum of junction gaps/overlaps. 
    #
    # The remaining fraction (1-junction_priority) will go towards minimizing the absolute value of all jaw offsets at each angle.

    #This function works by iterating through a set of possible calibration points (from -1 mm to 1mm across isocentre  in x/y direction) and
    #calculating the new jaw offsets each time and subsequent cost function
    #the cost function will be stored for each iteration, and finally, the cal point giving the minimum cost will be returned

    x1_iters = np.linspace(-1,1,31)
    x2_iters = np.linspace(-1,1,31)
    y1_iters = np.linspace(-1,1,21)
    y2_iters = np.linspace(-1,1,21)
    cost_vals = np.zeros((31,31,21,21))    #save as 2d grid with first dimension = x, second dimension = y

    #so for each iteration, first calculate the new offsets after shifting each jaw by respective amount
    #assume x and y vectors are in same direction as image vectors (so y1 > y2 in image - aka if calibration iso shifts by -1, then y1 would increase and y2 would decrease)
    if lrfc_folder is not None:
        use_lrfc = True
        lrfc_vals = []
        lrfc_field_sizes = []
        for file in os.listdir(lrfc_folder):
            lrfc_file = os.path.join(lrfc_folder, file)
            lrfc_points, _, _ = lrfc(lrfc_file)
            lrfc_vals.append(lrfc_points["rad_disp"])
            lrfc_field_sizes.append(lrfc_points["field_size"])
    else:
        use_lrfc = False

    #in service mode, jaws must be calibrated at g = 0 and c = 0, so need to calculate the new offsets in terms of shift from original offsets at g0c0 to iso
    for x1_ind, x1 in enumerate(x1_iters):
        for y1_ind, y1 in enumerate(y1_iters):
            for y2_ind, y2 in enumerate(y2_iters):
                for x2_ind, x2 in enumerate(x2_iters):
                    new_offsets = deepcopy(offsets)
                    for g in offsets.keys():
                        for c in offsets[g].keys():
                            if c == "iso":
                                continue
                            new_offsets[g][c]["x1"] = offsets[g][c]["x1"] - offsets[0][0]["x1"] + x1   #difference in offset from the calibration position + the cal position offset from isocentre
                            new_offsets[g][c]["x2"] = offsets[g][c]["x2"]- offsets[0][0]["x2"] + x2

                            new_offsets[g][c]["y1"] = offsets[g][c]["y1"]- offsets[0][0]["y1"] + y1
                            new_offsets[g][c]["y2"] = offsets[g][c]["y2"]- offsets[0][0]["y2"] + y2

                    #now compute the cost
                    cost = calculate_cost(new_offsets, offsets, use_lrfc, lrfc_vals, junction_priority=junction_priority, optimize_junctions=optimize_junctions)
                    cost_vals[x1_ind, x2_ind, y1_ind, y2_ind] = cost


     #best cost = minimum value
    opt_offset_ind = np.argwhere(cost_vals == np.amin(cost_vals))

    opt_offset_x1 = x1_iters[opt_offset_ind[0,0]]
    opt_offset_x2 = x2_iters[opt_offset_ind[0,1]]
    opt_offset_y1 = y1_iters[opt_offset_ind[0,2]]
    opt_offset_y2 = y2_iters[opt_offset_ind[0,3]]



    #make plots of cost vs. collimator points, varying two at a time (with others at optimal values)

    
    fig, ax = plt.subplots(nrows=1, ncols=2, figsize=(15, 15))
    ax[0].imshow(cost_vals[:,:,opt_offset_ind[0,2], opt_offset_ind[0,3]], cmap='rainbow')
    x_ticks = [2.5, 5, 7.5, 10, 12.5, 15, 17.5, 20]
    y_ticks = [2.5, 5, 7.5, 10, 12.5, 15, 17.5, 20]
    x_labels = []
    y_labels = []
    ax[0].set_xticks(x_ticks)
    ax[0].set_yticks(y_ticks)

    ax[1].set_xticks(x_ticks)
    ax[1].set_yticks(y_ticks)
  
    for i in range(len(x_ticks)):
        x_labels.append(round(x1_iters[int(x_ticks[i])],1))
    for i in range(len(y_ticks)):   
        y_labels.append(round(x2_iters[int(y_ticks[i])],1))
    ax[0].set_xticklabels(x_labels)
    ax[0].set_yticklabels(y_labels)
    ax[0].set_xlabel("X1 Displacement from Iso (mm)")
    ax[0].set_ylabel("X2 Displacement from Iso (mm)")

    #also show the cost values with colormap levelled
    vmax = np.amax(cost_vals[:,:,opt_offset_ind[0,2], opt_offset_ind[0,3]]) - 0.95 * (np.amax(cost_vals[:,:,opt_offset_ind[0,2], opt_offset_ind[0,3]]) - np.amin(cost_vals[:,:,opt_offset_ind[0,2], opt_offset_ind[0,3]]))
    ax[1].imshow(cost_vals[:,:,opt_offset_ind[0,2], opt_offset_ind[0,3]], cmap='rainbow', vmax=vmax)
    ax[1].set_xticklabels(x_labels)
    ax[1].set_yticklabels(y_labels)
    ax[1].set_xlabel("X1 Displacement from Iso (mm)")
    ax[1].set_ylabel("X2 Displacement from Iso (mm)")

    fig.savefig(os.path.join(os.getcwd(), f"U{unit_num}_Output", f"optimal_x1_x2_{datetime.datetime.now().strftime("%Y-%m-%d_%H_%M_%S")}"))
    #plt.show()
    del fig

 

   #now plot y1,y2 cost
    fig, ax = plt.subplots(nrows=1, ncols=2, figsize=(15, 15))
    ax[0].imshow(cost_vals[opt_offset_ind[0,0], opt_offset_ind[0,1],:,:], cmap='rainbow')
    x_ticks = [2.5, 5, 7.5, 10, 12.5, 15, 17.5, 20]
    y_ticks = [2.5, 5, 7.5, 10, 12.5, 15, 17.5, 20]
    x_labels = []
    y_labels = []
    ax[0].set_xticks(x_ticks)
    ax[0].set_yticks(y_ticks)

    ax[1].set_xticks(x_ticks)
    ax[1].set_yticks(y_ticks)

    for i in range(len(x_ticks)):
        x_labels.append(round(x1_iters[int(x_ticks[i])],1))
    for i in range(len(y_ticks)):   
        y_labels.append(round(x2_iters[int(y_ticks[i])],1))
    ax[0].set_xticklabels(x_labels)
    ax[0].set_yticklabels(y_labels)
    ax[0].set_xlabel("Y1 Displacement from Iso (mm)")
    ax[0].set_ylabel("Y2 Displacement from Iso (mm)")

    #also show the cost values with colormap levelled
    vmax = np.amax(cost_vals[opt_offset_ind[0,0], opt_offset_ind[0,1],:,:]) - 0.95 * (np.amax(cost_vals[opt_offset_ind[0,0], opt_offset_ind[0,1],:,:]) - np.amin(cost_vals[opt_offset_ind[0,0], opt_offset_ind[0,1],:,:]))
    ax[1].imshow(cost_vals[opt_offset_ind[0,0], opt_offset_ind[0,1],:,:], cmap='rainbow', vmax=vmax)
    ax[1].set_xticklabels(x_labels)
    ax[1].set_yticklabels(y_labels)
    ax[1].set_xlabel("Y1 Displacement from Iso (mm)")
    ax[1].set_ylabel("Y2 Displacement from Iso (mm)")
    fig.savefig(os.path.join(os.getcwd(), f"U{unit_num}_Output", f"optimal_y1_y2_{datetime.datetime.now().strftime("%Y-%m-%d_%H_%M_%S")}"))
    #plt.show()
    del fig



    #recalculate optimal offsets
    new_offsets = deepcopy(offsets)
    for g in offsets.keys():
        for c in offsets[g].keys():
            if c == "iso":
                continue
            new_offsets[g][c]["x1"] = offsets[g][c]["x1"] - offsets[0][0]["x1"] + opt_offset_x1   #difference in offset from the calibration position + the cal position offset from isocentre
            new_offsets[g][c]["x2"] = offsets[g][c]["x2"]- offsets[0][0]["x2"] + opt_offset_x2

            new_offsets[g][c]["y1"] = offsets[g][c]["y1"]- offsets[0][0]["y1"] + opt_offset_y1
            new_offsets[g][c]["y2"] = offsets[g][c]["y2"]- offsets[0][0]["y2"] + opt_offset_y2

    disp_x1 = new_offsets[0][0]["x1"] - offsets[0][0]["x1"]
    disp_x2 = new_offsets[0][0]["x2"] - offsets[0][0]["x2"]
    disp_y1 = new_offsets[0][0]["y1"] - offsets[0][0]["y1"]
    disp_y2 = new_offsets[0][0]["y2"] - offsets[0][0]["y2"]
    #now calculate new lrfc val for all lrfc images checked
    if use_lrfc:
        new_lrfcs = []
        for lrfc_val in lrfc_vals:
            new_rad_light_y = lrfc_val[0] + (disp_y1/2 + -disp_y2/2) 
            new_rad_light_x = lrfc_val[1] + (-disp_x1/2 + disp_x2/2)
            new_lrfcs.append([new_rad_light_y, new_rad_light_x])
    #want to write this data to a csv:

    with open(os.path.join(os.getcwd(), f"U{unit_num}_Output", f"jaws_and_junctions_{datetime.datetime.now().strftime("%Y-%m-%d_%H_%M_%S")}.csv"), 'w', newline='') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow([f"Offsets"])
        writer.writerow(["", f"Current", "Optimal"])
        writer.writerow(["x1", str(offsets[0][0]["x1"]), str(opt_offset_x1)])
        writer.writerow(["x2", str(offsets[0][0]["x2"]), str(opt_offset_x2)])
        writer.writerow(["y1", str(offsets[0][0]["y1"]), str(opt_offset_y1)])
        writer.writerow(["y2", str(offsets[0][0]["y2"]), str(opt_offset_y2)])
        writer.writerow(["Junction", "Original Offset", "Final Offset"])

        #calculate the junctions
        g0c90_x1 = offsets[0][90]["x1"]
        g180c90_x1 = offsets[180][90]["x1"]

        g0c90_x1_final = new_offsets[0][90]["x1"]
        g180c90_x1_final = new_offsets[180][90]["x1"]
        for g in [50, 130, 310, 230]:    #just the breast tangent angles for calculating junctions
            lower_x2 = offsets[g][90]["x2"]
            junction_gap_0 = lower_x2 + g0c90_x1  #adding together will give the total error from perfect junction (whether it's a gap or an overlap)
            junction_gap_180 = lower_x2 + g180c90_x1

            lower_x2_final = new_offsets[g][90]["x2"]
            junction_gap_0_final = lower_x2_final + g0c90_x1_final  #adding together will give the total error from perfect junction (whether it's a gap or an overlap)
            junction_gap_180_final = lower_x2_final + g180c90_x1_final

            #now add these junctions to the csv
            writer.writerow([f"g0c90_x1 and g{g}c90_x2", junction_gap_0, junction_gap_0_final])
            writer.writerow([f"g180c90_x1 and g{g}c90_x2", junction_gap_180, junction_gap_180_final])
        #now that junctions have been included, add all the offset values
        if use_lrfc:
            writer.writerow(["","",""])
            for f,field_size in enumerate(lrfc_field_sizes):
                writer.writerow([f"Radiation Light Field Coincidence ({field_size}X{field_size})", "Original", "Final"])

                writer.writerow(["Y", lrfc_vals[f][0],new_lrfcs[f][0]])
                writer.writerow(["X", lrfc_vals[f][1],new_lrfcs[f][1]])

        writer.writerow(["","",""])
        writer.writerow(["Jaw Displacements from Isocentre"])
        writer.writerow(["","",""])



        writer.writerow(["Gantry Angle","Collimator Angle","X1", "", "X2", "", "Y1", "", "Y2", ""])
        writer.writerow(["","","Original", "Final","Original", "Final","Original", "Final","Original", "Final"])
        for g in offsets.keys():
            for c in offsets[g].keys():
                if c == "iso":
                    continue
                writer.writerow([g,c,offsets[g][c]["x1"],new_offsets[g][c]["x1"], offsets[g][c]["x2"],new_offsets[g][c]["x2"], offsets[g][c]["y1"],new_offsets[g][c]["y1"], offsets[g][c]["y2"],new_offsets[g][c]["y2"]])
        if jaw_offsets is not None:
            writer.writerow(["","",""])
            writer.writerow(["Asymmetric Jaw Measurements"])
            writer.writerow(["","",""])
            writer.writerow(["X1"])
            for pos in jaw_offsets["x1"].keys():
                writer.writerow([pos, jaw_offsets["x1"][pos]])
            writer.writerow(["","",""])

            writer.writerow(["X2"])
            for pos in jaw_offsets["x2"].keys():
                writer.writerow([pos, jaw_offsets["x2"][pos]])
            writer.writerow(["","",""])

            writer.writerow(["Y1"])
            for pos in jaw_offsets["y1"].keys():
                writer.writerow([pos, jaw_offsets["y1"][pos]])
            writer.writerow(["","",""])

            writer.writerow(["Y2"])
            for pos in jaw_offsets["y2"].keys():
                writer.writerow([pos, jaw_offsets["y2"][pos]])
            

    return tuple((opt_offset_x1, opt_offset_x2, opt_offset_y1, opt_offset_y2)), new_offsets

def predict_optimal_encoders(unit_num, junction_priority, img_folder, jaw_pos_folder, enc_img_folder, enc_iso_img_path, lrfc_folder, optimize_junctions=True):

    if not os.path.exists(os.path.join(os.getcwd(), f"U{unit_num}_Output")):
        os.mkdir(os.path.join(os.getcwd(), f"U{unit_num}_Output"))

    #first collect imgs for closed jaws:
    junc_img_dict = sort_junc_img_dict(img_folder)
    #also get images for asymmetric jaw positions
    if jaw_pos_folder is not None:
        jaw_img_dict = sort_jaw_img_dict(jaw_pos_folder)


    #fit_encoder_vs_pixel_funcs(enc_img_folder, enc_iso_img_path, unit_num=unit_num, optimal_cal=[0.1, 0.1, -0.5, -0.3])
    # #now want to define the offset of each 1/4 blocked beam's jaw from isocentre at each gantry/collimator combination
    junc_offsets = get_junc_offsets(junc_img_dict, unit_num)
    if jaw_pos_folder is not None:
        isocentre = junc_offsets[0]["iso"]
        jaw_offsets = get_jaw_offsets(jaw_img_dict, isocentre)
    else:
        jaw_offsets = None

    # #now find the optimal calibration point (relative to g = 0, c = 0 isocentre image) to be used for calibration
    optimal_cal, new_offsets = get_opt_origin(junc_offsets, jaw_offsets, junction_priority, unit_num, lrfc_folder=lrfc_folder, optimize_junctions=optimize_junctions)    #x1,x2,y1,y2
    print(f"Optimal Calibration Shift: {optimal_cal}")
    # optimal_cal = [0.5,1,-0.5,-1]

    #now get jaw images to use for encoder-jaw correlations

    fit_encoder_vs_pixel_funcs(enc_img_folder, enc_iso_img_path, unit_num=unit_num, optimal_cal=optimal_cal)




unit_num=4
junction_priority=0.7
optimize_junctions = True
date="dec12"
pre_or_post = "pre"

encoder_dic = define_encoder_dict(unit_num)
img_folder = os.path.join(os.getcwd(), "Images", f"U{unit_num}_{pre_or_post}_{date}")
lrfc_folder = os.path.join(os.getcwd(), "Images", f"U{unit_num}_lrfc_{pre_or_post}_{date}")

enc_img_folder = os.path.join(os.getcwd(), "Images", f"U{unit_num}_encoders_{date}")
enc_iso_img_path = os.path.join(os.getcwd(), "Images", f"U{unit_num}_iso_encoder_{date}.dcm")

jaw_pos_folder = os.path.join(os.getcwd(), "Images", f"U{unit_num}_jaws_{pre_or_post}_{date}")

predict_optimal_encoders(unit_num, junction_priority, img_folder, jaw_pos_folder, enc_img_folder, enc_iso_img_path, lrfc_folder, optimize_junctions=optimize_junctions)




    
print("Program Finished Successfully")