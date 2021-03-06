from moviepy.editor import VideoFileClip
from IPython.display import HTML
import numpy as np
import cv2
import pickle
import glob
from threshold import threshold
from line import line

# Read in the saved objpoints and imgpoints
dist_pickle = pickle.load(open("./calibration_pickle.p","rb"))
mtx = dist_pickle["mtx"]
dist = dist_pickle["dist"]

# Global variable for line
line_dec = line(nWindows = 9, Margin = 100, Minpix = 50)

def process_image(img):

    # STEP2) Apply a distortion correction to raw images.
    # Undistort the image and save in output_images
    img = cv2.undistort(img,mtx,dist,None,mtx)

    # STEP3) Use color transforms and gradients to create a thresholded binary image.
    thrshFunc = threshold()
    thresholdedBinary = np.zeros_like(img[:,:,0])
    grad_x_binary = thrshFunc.abs_sobel_thresh(img, orient='x', thresh=(12,255))
    mag_binary = thrshFunc.mag_thresh(img, sobel_kernel=3, mag_thresh=(30,255))
    color_binary = thrshFunc.color_threshold(img, sthresh=(100,255))
    thresholdedBinary[((grad_x_binary == 1) | (mag_binary == 1) | (color_binary == 1))] = 255

    # STEP4) Apply a perspective transform to rectify binary image ("birds-eye view").
    img_size = (img.shape[1], img.shape[0]) # (x length, y length) of the image.
    src = np.float32([ 
        [ (img_size[0] / 2) - 55,   img_size[1] / 2 + 100],
        [ (img_size[0] / 6) - 10,   img_size[1]          ],
        [ (img_size[0] * 5/6) + 60, img_size[1]          ],
        [ (img_size[0] / 2) + 55,   img_size[1] / 2 + 100]
    ])

    dst = np.float32([
        [ img_size[0] / 4,   0 ],
        [ img_size[0] / 4,   img_size[1]],
        [ img_size[0] * 3/4, img_size[1]],
        [ img_size[0] * 3/4, 0]
    ])

    # Perform the perspective transform.
    M = cv2.getPerspectiveTransform(src, dst)
    Minv = cv2.getPerspectiveTransform(dst, src)
    warped = cv2.warpPerspective(thresholdedBinary,M,img_size,flags=cv2.INTER_LINEAR)

    # STEP5) Detect lane pixels and fit to find the lane boundary.
    leftx, lefty, rightx, righty, out_img = line_dec.find_lane_pixels(warped)
    left_fitx, right_fitx, yvals, out_img = line_dec.fit_polynomial(warped, leftx, lefty, rightx, righty, out_img)

    # STEP6) Determine the curvature of the lane and vehicle position with respect to center.
    # Choose the maximum y-value, corresponding to the bottom of the image and calculate the left curverad.
    # Define conversions in x and y from pixels space to meters
    ym_per_pix = 30/720 # meter per pixel in y dimension
    xm_per_pix = 3.7/700 # meter per pixel in x dimension
    left_curverad, right_curverad = line_dec.measure_curvature_pixels(leftx, lefty, rightx, righty, yvals, ym_per_pix, xm_per_pix)

    # Sanity Check
    left_curverad, right_curverad, left_fitx, right_fitx = line_dec.sanity_check(left_curverad, right_curverad, left_fitx, right_fitx, xm_per_pix)

    # calculate the offset of the car on the road
    camera_center = (left_fitx[-1] + right_fitx[-1])/2
    center_diff = (camera_center-warped.shape[1]/2)*xm_per_pix 
    side_pos = 'left'
    if center_diff <= 0:
        side_pos = 'right'

    # STEP7) Warp the detected lane boundaries back onto the original image.
    window_width = 25 # It is used to determin the width of left and right line.
    # I detect (x,y) of left_lane, right_lane, and middle_marker, and then I will draw polygons filled with a color. It displays as a lane. 
    left_lane = np.array(list(zip(np.concatenate((left_fitx-window_width/2,left_fitx[::-1]+window_width/2), axis=0), np.concatenate((yvals,yvals[::-1]), axis=0))),np.int32)
    right_lane = np.array(list(zip(np.concatenate((right_fitx-window_width/2,right_fitx[::-1]+window_width/2), axis=0), np.concatenate((yvals,yvals[::-1]),axis=0))),np.int32)
    middle_marker = np.array(list(zip(np.concatenate((left_fitx+window_width/2,right_fitx[::-1]-window_width/2), axis=0), np.concatenate((yvals,yvals[::-1]),axis=0))),np.int32)

    # Draw the lanes and the middle marker between left lane and right lane.
    road = np.zeros_like(img)
    road_bkg = np.zeros_like(img)
    cv2.fillPoly(road,[left_lane],color=[255,0,0])
    cv2.fillPoly(road,[right_lane],color=[255,0,0])
    cv2.fillPoly(road,[middle_marker],color=[0,0,255])
    # Draw a white left lane and a right lane in background image.
    cv2.fillPoly(road_bkg,[left_lane],color=[255,255,255])
    cv2.fillPoly(road_bkg,[right_lane],color=[255,255,255])

    road_warped = cv2.warpPerspective(road,Minv,img_size,flags=cv2.INTER_LINEAR)
    road_warped_bkg = cv2.warpPerspective(road_bkg,Minv,img_size,flags=cv2.INTER_LINEAR)

    # Overlap the lanes to the background.
    base = cv2.addWeighted(img, 1.0, road_warped_bkg, -1.0, 0.0)
    result = cv2.addWeighted(base, 1.0, road_warped, 1.0, 0.0)

    # Output visual display of the lane boundaries and numerical estimation of lane curvature and vehicle position.

    # I choose left curverad as a radius of curvature. 
    cv2.putText(result, 'Radius of Curvature = '+str(round(left_curverad,3))+'(m)',(50,50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    cv2.putText(result, 'Vehicle is '+str(abs(round(center_diff,3)))+'m '+side_pos+' of center',(50,100), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

    return result

Output_video = './tracked_project_video.mp4'
Input_video = './project_video.mp4'

clip1 = VideoFileClip(Input_video)
video_clip = clip1.fl_image(process_image) 
video_clip.write_videofile(Output_video,audio=False)