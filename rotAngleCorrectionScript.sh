#!/bin/bash  

# Generate comparison data
#mkdir /home/smcmich1/data/angleCorrectionTest/oldResults
#lronac2mosaic.py -t 4 -o /home/smcmich1/data/angleCorrectionTest/oldResults --keep ~/data/M123514622LE.IMG ~/data/M123514622RE.IMG
#exit 0

# original file offset = -46, -28


# Move to test directory
#mkdir /home/smcmich1/data/angleCorrectionTest
cd /home/smcmich1/data/angleCorrectionTest

# Copy and convert the two test cubes
#lronac2isis from=~/data/M123514622LE.IMG to=M123514622LE.cub
#lronac2isis from=~/data/M123514622RE.IMG to=M123514622RE.cub

# Perform pre-processing steps
#lronaccal from=M123514622LE.cub to=M123514622LE.lronaccal.cub
#lronaccal from=M123514622RE.cub to=M123514622RE.lronaccal.cub

#lronacecho from=M123514622LE.lronaccal.cub to=M123514622LE.lronaccal.lronacecho.cub
#lronacecho from=M123514622RE.lronaccal.cub to=M123514622RE.lronaccal.lronacecho.cub

# Apply corrected SPICE data
/home/smcmich1/repo/lronacPipeline/positionCorrector.py --input M123514622LE.lronaccal.lronacecho.cub --output M123514622LE.corrected.cub
/home/smcmich1/repo/lronacPipeline/positionCorrector.py --input M123514622RE.lronaccal.lronacecho.cub --output M123514622RE.corrected.cub --spk reCorrectedSpk.bsp

# TODO: Handle kernel-spanning data!

# Now compute the corrected rotation
/home/smcmich1/repo/lronacPipeline/rotationCorrector.py --left M123514622LE.corrected.cub --right M123514622RE.corrected.cub --output M123514622RE.rotCorrected.cub --spk reCorrectedSpk.bsp --keep

# TEST: Compare rotations here!
#/home/smcmich1/repo/StereoPipeline/src/asp/Tools/lronacAngleSolver ~/data/angleCorrectionTest/M123514622LE.corrected.cub ~/data/angleCorrectionTest/M123514622RE.rotCorrected.cub 

# Noproj the corrected data
noproj from=M123514622LE.corrected.cub    to=M123514622LE.corrected.noproj.cub    match=M123514622LE.corrected.cub specs=noprojInstruments_fullRes.pvl
noproj from=M123514622RE.rotCorrected.cub to=M123514622RE.rotCorrected.noproj.cub match=M123514622LE.corrected.cub specs=noprojInstruments_fullRes.pvl 

#cp M123514622LE.corrected.noproj.cub M123514622LE.mosaic.cub
#handmos from=M123514622RE.rotCorrected.noproj.cub mosaic=M123514622LE.mosaic.cub outsample=0 outline=0 matchbandbin=FALSE priority=ontop

# TODO: Generate DEM, compare to ASU/LOLA



