#!/usr/bin/python

import math
import json
import http.client
import os
import threading
from  PIL import Image

# using Distance figures out how big the Earth should look
def imgSize(d):
    const = ((1024-158) / 1024) * (1386540)
    return (const/d)



def latLngtoXY(sinLa,cosLa,sinLn,cosLn,sinCl,cosCl):
    x = sinLn*cosLa
    y1 = cosLn*cosLa
    z1 = sinLa
    z = z1*cosCl - y1*sinCl 
    y = z1*sinCl + y1*cosCl
    return (x,y,z)

# takes 2 DSCOVR images and merges them (badly)
# assume lng is between centroids of both
# lng of 1st centroid is > lng of 2nd centroid
# TODO: correct for oblateness
#       measure luminance of 2 input images and correct output
#       supersampling
def tweenFiles(first,last,outfile,lng):
    # open image1 read all the info
    earth1 = Image.open(first)
    (clat1,clng1,distance1) = getInfo(earth1.info) 
    (width1,height1) = earth1.size
    pixels1 = earth1.load()
    sinLa1 = math.sin(clat1*math.pi/180)
    cosLa1 = math.cos(clat1*math.pi/180) 
    esize1 = imgSize(distance1)
    width1 /= 2
    height1 /= 2

    # open image2 read and compute info
    earth2 = Image.open(last)
    (clat2,clng2,distance2) = getInfo(earth2.info)
    (width2,height2) = earth2.size
    pixels2 = earth2.load()
    sinLa2 = math.sin(clat2*math.pi/180)
    cosLa2 = math.cos(clat2*math.pi/180) 
    esize2 = imgSize(distance2)
    width2 /= 2
    height2 /= 2

    # figure out weights for images
    lngdiff = clng1 - clng2
    #print(str(lngdiff) + " " + str(clng1) + " " + str(clng2))
    if(lngdiff < 0):
        lngdiff = lngdiff + 360

    diff1 = clng1 - lng
    if(diff1 < 0):
        diff1 = diff1 + 360      

    diff2 = lng - clng2
    if(diff2 < 0):
        diff2 = diff2 + 360
    weight1 = diff2 / lngdiff
    weight2 = diff1 / lngdiff


    # find intermediate centroid
    clat = (clat1 * weight1) + (clat2 * weight2)
    distance = (distance1 * weight1) + (distance2 * weight2)
    #print((clat,clat1,clat2))
    clat = -clat * math.pi / 180
    sinClav = math.sin(clat)
    cosClav = math.cos(clat)
    
    # create output image 
    ox = 2048
    oy = 2048
    ox2 = ox /2
    oy2 = oy /2
    img = Image.new('RGB', (ox,oy), color='black')
    pixelsOut = img.load()
    esize = imgSize(distance)
    
    lngRad = lng *math.pi / 180

    clng1 = clng1 * math.pi / 180
    clng2 = clng2 * math.pi / 180

    # now iterate over every pixel
    for x in range(0,ox):
        dx = (x - ox2) / (ox2*esize) 
        for y in range(0,oy):
            dy = -(y - oy2) / (oy2*esize)
            rad = dx*dx + dy*dy
            if(rad > 1):
                continue #pixel is looking at space
            dzt = math.sqrt(1-rad)
            # now translate this to lat/lng on our projected sphere    
            # might need to change signs
            dz = sinClav*dy + cosClav*dzt
            dy = cosClav*dy - sinClav*dzt
            tLat = math.asin(dy) 
            tLng = math.atan2(dx,dz)+lngRad
            if(tLng<0):
                tLng += math.pi * 2
            #print((tLat,tLng,tLat*180/math.pi,tLng*180/math.pi))
            # now look for pixel coordinates on each image
            sinCl = math.sin(tLat)
            cosCl = math.cos(tLat)
   
            # now for each sphere, figure out what x/y the lat/lng corresponds to
            # image1
            sinLn = math.sin(tLng - clng1)
            cosLn = math.cos(tLng - clng1)
            (sx,sy,sz) = latLngtoXY(sinCl,cosCl,sinLn,cosLn,sinLa1,cosLa1)
            #print((sx,sy,sz))
            pixel1 = (0,0,0)
            if(sy > 0):
                sx = int((sx * width1 * esize1) + width1)
                sz = int(-(sz * height1 * esize1) + height1)
                pixel1 = pixels1[sx,sz]
                                   
            # image2
            sinLn = math.sin(tLng - clng2)
            cosLn = math.cos(tLng - clng2)
            (sx,sy,sz) = latLngtoXY(sinCl,cosCl,sinLn,cosLn,sinLa2,cosLa2)
            pixel2 = (0,0,0)
            if(sy > 0):
                sx = int((sx * width2 * esize2) + width2)
                sz = int(-(sz * height2 * esize2) + height2)
                pixel2 = pixels2[sx,sz]

            # now pick pixels
            if(pixel1[1] > 0):
                if(pixel2[1] > 0):
                    pixel = (int(math.sqrt(pixel1[0]*pixel1[0]* weight1 + pixel2[0] *pixel2[0] * weight2)), int(math.sqrt(pixel1[1]*pixel1[1]*weight1 + pixel2[1]*pixel2[1]*weight2)), int(math.sqrt(pixel1[2]*pixel1[2]*weight1 + pixel2[2]*pixel2[2]*weight2)))
                else:
                    pixel = pixel1
            else:
                pixel = pixel2
            pixelsOut[x,y] = pixel
    img.save(outfile)
    
 

# returns important image info
def getInfo(info):
    comment = json.loads(info['Comment'].replace('\'','"'))
    clat = float(comment['centroid_coordinates']['lat'])
    clng = float(comment['centroid_coordinates']['lon'])
    dx = comment['dscovr_j2000_position']['x']
    dy = comment['dscovr_j2000_position']['y']
    dz = comment['dscovr_j2000_position']['z']
    distance = math.sqrt(dx*dx + dy*dy + dz*dz)
    return (clat,clng,distance)

# unroll image and place onto cylindrical projection
def map_transform(inputFile,outputFile):
    earth = Image.open(inputFile)
    (clat,clng,distance) = getInfo(earth.info)
    (width,height) = earth.size
    width = width / 2
    height = height / 2
    # need to compute this based on distance?

    earth = earth.convert('RGB')
    pixelse = earth.load()
    print (earth.getbands())
    esize = imgSize(distance)
    print(esize)

    ox = 1000
    oy = 500

    img = Image.new('RGB', (ox,oy), color='black')
    pixelsm = img.load()

    clat = clat * math.pi / 180
    clng = clng * math.pi / 180
    sinCl = math.sin(clat)
    cosCl = math.cos(clat)
    for x in range(0, ox):
        lng = (x * math.pi *2/ ox) - clng 
        sinLn = math.sin(lng)
        cosLn = math.cos(lng)
        for y in range(0,oy):
            lat = (y+(oy/2)) * math.pi / oy
            sinLa = math.sin(lat)
            cosLa = math.cos(lat)
            (sx,sy,sz) = latLngtoXY(sinLa,cosLa,sinLn,cosLn,sinCl,cosCl)
            #print((sx,sy,sz))
            if(sy > 0):
                sx = int((sx * width * esize) + width)
                sz = int(-(sz * height * esize) + height)
                #print( str(sx) + " " + str(sy) + " " + str(pixelse[sx,sy]))
                pixelsm[x,y] = pixelse[sx,sz]
            else:
                pixelsm[x,y] = (100,100,100)     
    img.save(outputFile)

renderThread = None
# https://epic.gsfc.nasa.gov/api/natural/all
conn = http.client.HTTPSConnection("epic.gsfc.nasa.gov")
print("GET /api/natural/all")
conn.request("GET", "/api/natural/all")
r1 = conn.getresponse()
dates = json.loads(r1.read())
conn.close()
lon = None
prev_img = None
frame_count = 1
dates_to_render = ("2019-04-28","2019-04-29","2019-04-30","2019-05-01","2019-05-02","2019-05-03","2019-05-04","2019-05-05")
for date in dates_to_render:
    conn.request("GET", "/api/natural/date/" + date)
    r1 = conn.getresponse()
    data = json.loads(r1.read())
    for datum in data:   
        img_lon = datum["centroid_coordinates"]["lon"]
        dateParts = date.split("-")
        imagename = datum["image"]
        imageFile = imagename + ".png"
        if not os.path.exists(imageFile):
            print("Downloading " + imageFile)
            conn = http.client.HTTPSConnection("epic.gsfc.nasa.gov")
            conn.request("GET","/archive/natural/" + dateParts[0] + "/" + dateParts[1] + "/" + dateParts[2] + "/png/" + imageFile)
            r1 = conn.getresponse()
            imgData = r1.read()
            fp = open(imageFile, "wb")
            fp.write(imgData)
            fp.close()
            conn.close()

        if lon == None:
            lon = img_lon
            prev_img = imageFile
            
            fp = open("frame_0.png","wb")
            fp.write(imgData)
            fp.close()
        else:
            # generate frames until lon < img_lon (because rotate from e->w)
            print("Tweening loop " + str(lon) + " " + str(img_lon))
            mdiff = ((lon - img_lon) + 360) % 360
            while (mdiff < 180):
                print("Tweening " + prev_img + " " + imageFile + " " + str(lon) + " " + str(frame_count))
                if(not os.path.exists("frame_" + str(frame_count) + ".png")):
                    tweenFiles(prev_img,imageFile,"frame_" + str(frame_count) + ".png",lon)
                lon = lon - 2
                if(lon < -180):
                    lon += 360
                frame_count += 1
                mdiff = ((lon - img_lon) + 360) % 360
            # current image becomes previous
            prev_img = imageFile

