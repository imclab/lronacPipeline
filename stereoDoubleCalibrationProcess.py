#!/usr/bin/env python
# __BEGIN_LICENSE__
#  Copyright (c) 2009-2013, United States Government as represented by the
#  Administrator of the National Aeronautics and Space Administration. All
#  rights reserved.
#
#  The NGT platform is licensed under the Apache License, Version 2.0 (the
#  "License"); you may not use this file except in compliance with the
#  License. You may obtain a copy of the License at
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# __END_LICENSE__

import sys

import os, glob, optparse, re, shutil, subprocess, string, time

job_pool = [];

def man(option, opt, value, parser):
    print >>sys.stderr, parser.usage
    print >>sys.stderr, '''\
Applies the LROC offset from spacecraft position to an LROC cube's spice data
'''
    sys.exit()

class Usage(Exception):
    def __init__(self, msg):
        self.msg = msg

def add_job( cmd, num_working_threads=4 ):
    if ( len(job_pool) >= num_working_threads):
        job_pool[0].wait();
        job_pool.pop(0);
    print cmd;
    job_pool.append( subprocess.Popen(cmd, shell=True) );

def wait_on_all_jobs():
    print "Waiting for jobs to finish";
    while len(job_pool) > 0:
        job_pool[0].wait();
        job_pool.pop(0);


#--------------------------------------------------------------------------------

# TODO: Make this a standalone function!
# Get a single file ready to process
def prepareImgFile(inputPath, outputFolder):

    # Generate the appropriate paths in the output folder
    temp           = os.path.splitext(inputPath)[0] + '.cub'
    initialCubFile = os.path.join(outputFolder, os.path.basename(temp))
    temp           = os.path.splitext(inputPath)[0] + '.lronaccal.cub'
    calCubFile     = os.path.join(outputFolder, os.path.basename(temp))
    temp           = os.path.splitext(inputPath)[0] + '.lronaccal.lronacecho.cub'
    echoCubFile    = os.path.join(outputFolder, os.path.basename(temp))

    # Quit immediately if the output file already exists
    if os.path.exists(echoCubFile):
        return echoCubFile

    if not os.path.exists(initialCubFile):
        cmd = 'lronac2isis from= ' + inputPath + ' to= ' + initialCubFile
        print cmd
        os.system(cmd)

    if not os.path.exists(calCubFile):
        cmd = 'lronaccal from= ' + initialCubFile + ' to= ' + calCubFile
        print cmd
        os.system(cmd)

    if not os.path.exists(echoCubFile):
        cmd = 'lronacecho from= ' + calCubFile + ' to= ' + echoCubFile
        print cmd
        os.system(cmd)

    cmd = 'spiceinit from= ' + echoCubFile
    print cmd
    os.system(cmd)


    return echoCubFile




# Apply the position offset specified in the IK kernel to either an LE or RE camera.
def applyInterCameraPositionOffset(inputCubePath, outputCubePath, workingDirectory, forceOperation):

    # Quit immediately if the output file already exists
    if (not forceOperation) and (os.path.exists(outputCubePath)):
        print 'File ' + outputCubePath + ' already exists, skipping position offset correction.'
        return True

    # Run the process
    cmd = '/home/smcmich1/repo/lronacPipeline/positionCorrector.py --keep --input ' + inputCubePath + ' --output ' + outputCubePath + ' --workDir ' + workingDirectory
    print cmd
    os.system(cmd)

    # Check to make sure we actually created the file
    if not os.path.exists(outputCubePath):
        raise Exception('Position offset correction failed to create output file ' + outputCubePath + ' from input file ' + inputCubePath)

    return True



# Samples pixels pairs for bundle adjustment from the output of the stereo command.
# - Returns the output path.
def extractPixelPairsFromStereoResults(disparityImagePath, outputDirectory, outputFileName, sampleInterval, forceOperation):

    # Quit immediately if the output file already exists
    outputPixelPath = os.path.join(outputDirectory, outputFileName)
    if (not forceOperation) and (os.path.exists(outputPixelPath)):
        print 'File ' + outputPixelPath + ' already exists, skipping pixel pair sampling.'
        return outputPixelPath

    # Run the process
    cmd = '/home/smcmich1/repo/lronacPipelineBuild/pixelPairsFromStereo -i ' + disparityImagePath + ' -o ' + outputPixelPath + ' -p ' + str(sampleInterval)
    print cmd
    os.system(cmd)

    # Check to make sure we actually created the file
    if not os.path.exists(outputPixelPath):
        raise Exception('Pixel sampling failed to create output file ' + outputPixelPath + ' from input file ' + disparityImagePath)

    return outputPixelPath


# Applies a planet-centered rotation and correction to the nav data of a cube
# - If the CK and SPK paths are not specified, paths are automatically generated.
# - Set forceOperation to run the operation even if the output file already exists
def applyNavTransform(inputCubePath, outputCubePath, transformMatrixPath, workDir, ckPath, spkPath, forceOperation):

    # Quit immediately if the output file already exists
    if (not forceOperation) and (os.path.exists(outputCubePath)):
        print 'File ' + outputCubePath + ' already exists, skipping nav transform.'
        return True

    # Set up CK and SPK manual paths if they were specified
    ckLine  = ''
    spkLine = ''
    if (ckPath):
        ckLine  = ' --ck '  + ckPath
    if (spkPath):
        spkLine = ' --spk ' + spkPath

    # Execute the transformation command
    cmd = '/home/smcmich1/repo/lronacPipeline/rotationCorrector.py --keep --input ' + inputCubePath + ' --output ' + outputCubePath + ' --transformPath ' + transformMatrixPath + ' --workDir ' + workDir + ckLine + spkLine
    print cmd
    os.system(cmd)

    # Check to make sure we actually created the file
    if not os.path.exists(outputCubePath):
        raise Exception('Nav transform failed to create output file ' + outputCubePath + ' from input file ' + inputCubePath)

    return True


# Tries to compute the internal angle between an LE/RE image pair.
# - Output GDC points serve as a check to make sure the images are in roughly the correct place.
def checkAdjacentPairAlignment(leftInputPath, rightInputPath, outputDirectory, outputFileName, forceOperation):

    # Quit immediately if the output file already exists
    outputGdcPath = os.path.join(outputDirectory, outputFileName)
    if (not forceOperation) and (os.path.exists(outputGdcPath)):
        return True

    # Run the process
    cmd = '/home/smcmich1/repo/lronacPipelineBuild/lronacAngleSolver --outputPath dummy.txt --gdcPointsOutPath ' + outputGdcPath + ' ' + leftInputPath + ' ' + rightInputPath
    print cmd
    os.system(cmd)

    # Check to make sure we actually created the file
    if not os.path.exists(outputGdcPath):
        raise Exception('Adjacency check failed to create output file ' + outputGdcPath + ' from input files ' + leftInputPath + ' and ' + rightInputPath)

    return True


# Generate a modified IK kernel to adjust the rotation between an LE/RE camera pair.
def applyInterCameraPairRotation(leftInputPath, rightInputPath, newRotationPath, outputCubePath, ckPath, spkPath, forceOperation)

    # Quit immediately if the output file already exists
    if (not forceOperation) and (os.path.exists(outputCubePath)):
        print 'File ' + outputCubePath + ' already exists, skipping nav transform.'
        return True

    # Generate the new file
    cmd = '/home/smcmich1/repo/lronacPipeline/lronacCameraRotationCorrector.py --keep --output ' + outputCubePath + ' --rotation ' + newRotationPath + ' --left ' + leftInputPath + ' --right ' + rightInputPath + ' --ck ' + ckPath + ' --spk ' + spkPath 
    print cmd
    os.system(cmd)

    # Check to make sure we actually created the file
    if not os.path.exists(outputCubePath):
        raise Exception('Inter-camera rotation failed to create output file ' + outputCubePath + ' from input files ' + leftInputPath + ' and ' + rightInputPath)

    return True


# Calls stereo functions to generate a disparity image and returns the path to it.
def callStereoCorrelation(leftInputPath, rightInputPath, outputPrefix, correlationTimeout, forceOperation):

    # Quit immediately if the output file already exists
    disparityImagePath = stereoPrefixLeftCross + '-D.tif'
    if (not forceOperation) and (os.path.exists(disparityImagePath)):
        print 'File ' + disparityImagePath + ' already exists, skipping stereo computation.'
        return disparityImagePath

    # Stage 0 (fast)
    cmd = 'stereo_pprc ' + leftInputPath + ' ' + rightInputPath + ' ' + outputPrefix
    print cmd
    os.system(cmd)
    # Stage 1 (slow!)
    cmd = 'stereo_corr --cost-mode 0 --corr-timeout ' + str(correlationTimeout) + ' ' + leftInputPath + ' ' + rightInputPath + ' ' + outputPrefix
    print cmd
    os.system(cmd)

    # Check to make sure we actually created the file
    if not os.path.exists(outputCubePath):
        raise Exception('Stereo processing failed to create output file ' + disparityImagePath + ' from input files ' + leftInputPath + ' and ' + rightInputPath)

    return disparityImagePath


#--------------------------------------------------------------------------------

def main():

    print "Started stereoDoubleCalibrationProcess.py"

    try:
        try:
            usage = "usage: stereoDoubleCalibrationProcess.py TODO [--manual]\n  "
            parser = optparse.OptionParser(usage=usage)
            parser.add_option("--left",  dest="leftPath",  help="Path to LE .IMG file")
            parser.add_option("--right", dest="rightPath", help="Path to RE .IMG file")
            
            parser.add_option("--stereo-left", dest="stereoLeft", help="Path to LE .IMG file with overlapping view of --left file")
            parser.add_option("--stereo-right", dest="stereoRight", help="Path to RE .IMG file with overlapping view of --right file")
  
            # The default working directory path is kind of ugly...
            parser.add_option("--workDir", dest="workDir",  help="Folder to store temporary files in")
            parser.add_option("--lola",    dest="lolaPath", help="Path to LOLA DEM")

            parser.add_option("--outputL",  dest="outputPathLeft",        help="Where to write the output LE file.")
            parser.add_option("--outputR",  dest="outputPathRight",       help="Where to write the output RE file.")
            parser.add_option("--outputSL", dest="outputPathStereoLeft",  help="Where to write the output Stereo LE file.")
            parser.add_option("--outputSR", dest="outputPathStereoRight", help="Where to write the output Stereo RE file.")

            
            parser.add_option("--manual", action="callback", callback=man,
                              help="Read the manual.")
            parser.add_option("--keep", action="store_true", dest="keep",
                              help="Do not delete the temporary files.")
            (options, args) = parser.parse_args()

            #TODO: Use default and required tags above!
            if not options.leftPath: 
                parser.error("Need left input path")
            if not options.rightPath: 
                parser.error("Need right input path")
            if not options.stereoLeft: 
                parser.error("Need stereo left input path")
            if not options.stereoRight: 
                parser.error("Need stereo right input path")
            if not options.lolaPath: 
                parser.error("Need LOLA DEM path")
            if not options.outputPathLeft: 
                parser.error("Need left output path")
            if not options.outputPathRight: 
                parser.error("Need right output path")
            if not options.outputPathStereoLeft: 
                parser.error("Need stereo left output path")
            if not options.outputPathStereoRight: 
                parser.error("Need stereo right output path")

        except optparse.OptionError, msg:
            raise Usage(msg)

        print "Beginning processing....."

        startTime = time.time()

        outputFolder  = os.path.dirname(options.outputPathLeft)
        inputBaseName = os.path.basename(options.leftPath)
        tempFolder    = outputFolder + '/' + inputBaseName + '_stereoCalibrationTemp/'
        if (options.workDir):
            tempFolder = options.workDir
        if not os.path.exists(outputFolder):
            os.mkdir(outputFolder) 
        if not os.path.exists(tempFolder):
            os.mkdir(tempFolder)


        # Convert the input files from IMG files to spiceinit'ed cubes in the output folder
        spiceInitLeftPath        = prepareImgFile(options.leftPath,    tempFolder)
        spiceInitRightPath       = prepareImgFile(options.rightPath,   tempFolder)
        spiceInitStereoLeftPath  = prepareImgFile(options.stereoLeft,  tempFolder)
        spiceInitStereoRightPath = prepareImgFile(options.stereoRight, tempFolder)

        # DEBUG: Check angle solver on input LE/RE images!
        checkAdjacentPairAlignment(spiceInitLeftPath, spiceInitRightPath, tempFolder, 'pairGdcCheckPre.csv', False)

        #print 'QUITTING EARLY'
        #return 0 

        # Apply LE/RE LRONAC position offsets to each of the input files
        posOffsetCorrectedLeftPath = os.path.join(tempFolder, 'left.posOffsetCorrected.cub')
        thisWorkDir                = os.path.join(tempFolder, 'leftPosCorrectDir')
        applyInterCameraPositionOffset(spiceInitLeftPath, posOffsetCorrectedLeftPath, thisWorkDir, False)

        posOffsetCorrectedRightPath = os.path.join(tempFolder, 'right.posOffsetCorrected.cub')
        thisWorkDir                 = os.path.join(tempFolder, 'rightPosCorrectDir')
        applyInterCameraPositionOffset(spiceInitRightPath, posOffsetCorrectedRightPath, thisWorkDir, False)

        posOffsetCorrectedStereoLeftPath = os.path.join(tempFolder, 'stereoLeft.posOffsetCorrected.cub')
        thisWorkDir                      = os.path.join(tempFolder, 'stereoLeftPosCorrectDir')
        applyInterCameraPositionOffset(spiceInitStereoLeftPath, posOffsetCorrectedStereoLeftPath, thisWorkDir, False)

        posOffsetCorrectedStereoRightPath = os.path.join(tempFolder, 'stereoRight.posOffsetCorrected.cub')
        thisWorkDir                       = os.path.join(tempFolder, 'stereoRightPosCorrectDir')
        applyInterCameraPositionOffset(spiceInitStereoRightPath, posOffsetCorrectedStereoRightPath,  thisWorkDir, False)


        # Fail if required files are not present
        if (not os.path.exists(posOffsetCorrectedLeftPath)) or (not os.path.exists(posOffsetCorrectedRightPath)) or (not os.path.exists(posOffsetCorrectedStereoLeftPath)):
            print 'Missing required processed input files!  Processing stopped.'
            return 0


        # DEBUG: Check angle solver on input LE/RE images!
        checkAdjacentPairAlignment(posOffsetCorrectedLeftPath, posOffsetCorrectedRightPath, tempFolder, 'pairGdcCheckInitial.csv', False)

        #print 'QUITTING EARLY'
        #return 0 


        # Perform initial stereo step on two LE cubes to generate a large number of point correspondences
        stereoPrefixLeft   = os.path.join(tempFolder, 'stereoOutputLeft')
        disparityImageLeft = callStereoCorrelation(posOffsetCorrectedLeftPath, posOffsetCorrectedStereoLeftPath, stereoPrefixLeft, 400, False):

        # Perform initial stereo step on two RE cubes to generate a large number of point correspondences
        stereoPrefixRight   = os.path.join(tempFolder, 'stereoOutputRight')
        disparityImageRight = callStereoCorrelation(posOffsetCorrectedRightPath, posOffsetCorrectedStereoRightPath, stereoPrefixRight, 400, False):


        # Extract a small number of matching pixel locations from the disparity images ( < 300)
        pixelPairsLeftSmall = extractPixelPairsFromStereoResults(disparityImageLeft, tempFolder, 'stereoPixelPairsLeftSmall.csv', 800, False)
        pixelPairsRightSmall = extractPixelPairsFromStereoResults(disparityImageRight, tempFolder, 'stereoPixelPairsRightSmall.csv', 800, False)

        #print 'QUITTING EARLY'
        #return 0 



# TESTING - Perform cross-stereo matching of LE/RE cubes from opposite pairs

        # Crop each input cube to half its width
        # - Take the right half of the LE cubes and the left half of the RE cubes
        leftPosCorrectedCropped        = os.path.join(tempFolder, 'leftCropped.cub')
        rightPosCorrectedCropped       = os.path.join(tempFolder, 'rightCropped.cub')
        leftStereoPosCorrectedCropped  = os.path.join(tempFolder, 'leftStereoCropped.cub')
        rightStereoPosCorrectedCropped = os.path.join(tempFolder, 'rightStereoCropped.cub')

        if not os.path.exists(leftPosCorrectedCropped):
            cmd = 'crop sample=2531 from=' + posOffsetCorrectedLeftPath + ' to= ' + leftPosCorrectedCropped
            print cmd
            os.system(cmd)
        if not os.path.exists(rightPosCorrectedCropped):
            cmd = 'crop nsamples=2532 from=' + posOffsetCorrectedRightPath + ' to= ' + rightPosCorrectedCropped
            print cmd
            os.system(cmd)
        if not os.path.exists(leftStereoPosCorrectedCropped):
            cmd = 'crop sample=2531 from=' + posOffsetCorrectedStereoLeftPath + ' to= ' + leftStereoPosCorrectedCropped
            print cmd
            os.system(cmd)
        if not os.path.exists(rightStereoPosCorrectedCropped):
            cmd = 'crop nsamples=2532 from=' + posOffsetCorrectedStereoRightPath + ' to= ' + rightStereoPosCorrectedCropped
            print cmd
            os.system(cmd)


        # Use stereo command on two cross-pair cubes
        # - Timeouts are shorter on these since there is probably less image overlap
        
        # First is left in main pair to right in the stereo pair
        stereoPrefixLeftCross   = os.path.join(tempFolder, 'stereoOutputLeftCross')
        disparityImageLeftCross = callStereoCorrelation(leftPosCorrectedCropped, rightStereoPosCorrectedCropped, stereoPrefixLeftCross, 100, False):

        # Next is left in the stereo pair to right in the main pair
        stereoPrefixRightCross   = os.path.join(tempFolder, 'stereoOutputRightCross')
        disparityImageRightCross = callStereoCorrelation(leftStereoPosCorrectedCropped, rightPosCorrectedCropped, stereoPrefixRightCross, 100, False):


        # Extract a small number of matching pixel locations from the disparity images ( < 300)
        # - The pixels are extracted more densely because there is much less overlap area to work with.
        pixelPairsLeftCrossSmall = extractPixelPairsFromStereoResults(disparityImageLeftCross, tempFolder, 'stereoPixelPairsLeftCrossSmall.csv', 400, False)
        pixelPairsRightCrossSmall = extractPixelPairsFromStereoResults(disparityImageRightCross, tempFolder, 'stereoPixelPairsRightCrossSmall.csv', 400, False)


        #print 'QUITTING EARLY'
        #return 0 

# DONE TESTING




        # Compute all rotations and translations between the four cubes
        sbaOutputPrefix     = os.path.join(tempFolder, 'SBA_solution')
        smallGdcFile        = sbaOutputPrefix + "-outputGdcPoints.csv"
        localRotationPath   = sbaOutputPrefix + "-localRotationMatrix.csv"
        globalTransformPath = sbaOutputPrefix + "-globalTransformMatrix.csv"
        stereoRotationPath  = sbaOutputPrefix + "-stereoLocalRotationMatrix.csv"
        if not os.path.exists(globalTransformPath):
            cmd = '/home/smcmich1/repo/lronacPipelineBuild/lronacAngleDoubleSolver --outputPrefix ' + sbaOutputPrefix + ' --matchingPixelsLeftPath ' + pixelPairsLeftSmall + ' --matchingPixelsRightPath ' + pixelPairsRightSmall + ' --matchingPixelsLeftCrossPath ' + pixelPairsLeftCrossSmall +  ' --matchingPixelsRightCrossPath ' + pixelPairsRightCrossSmall + ' ' + posOffsetCorrectedLeftPath + ' ' + posOffsetCorrectedRightPath + ' ' + posOffsetCorrectedStereoLeftPath + ' ' + posOffsetCorrectedStereoRightPath
            #cmd = '/home/smcmich1/repo/lronacPipelineBuild/lronacAngleDoubleSolver --outputPrefix ' + sbaOutputPrefix + ' --matchingPixelsLeftPath ' + pixelPairsLeftSmall + ' --matchingPixelsRightPath ' + pixelPairsRightSmall + ' ' + posOffsetCorrectedLeftPath + ' ' + posOffsetCorrectedRightPath + ' ' + posOffsetCorrectedStereoLeftPath + ' ' + posOffsetCorrectedStereoRightPath
            print cmd
            os.system(cmd)
        else:
            print 'Skipping stereo transform calculation step'

        #print 'QUITTING EARLY'
        #return 0 

        # Apply the transform to the second camera pair!  The transform is in moon coordinates.
        tempLeftStereoPath = os.path.join(tempFolder, 'leftStereoAdjusted.cub')
        thisWorkDir        = os.path.join(tempFolder, 'stereoLeftStereoCorrection/')
        applyNavTransform(posOffsetCorrectedStereoLeftPath, tempLeftStereoPath, globalTransformPath, thisWorkDir, '', '', false)

        tempRightStereoPath = os.path.join(tempFolder, 'rightStereoAdjusted.cub')
        thisWorkDir         = os.path.join(tempFolder, 'stereoRightStereoCorrection/')
        applyNavTransform(posOffsetCorrectedStereoRightPath, tempRightStereoPath, globalTransformPath, thisWorkDir, '', '', false)

        # DEBUG: Check angle solver on stereo adjusted LE/RE images!
        checkAdjacentPairAlignment(tempLeftStereoPath, tempRightStereoPath, tempFolder, 'pairGdcCheckStereo.csv', False)

        #print 'QUITTING EARLY'
        #return 0 


        # Extract a large number of matching pixel locations (thousands) from the LE/LE and RE/RE stereo.
        # - Right now the skip is rows and columns
        pixelPairsLeftLarge = extractPixelPairsFromStereoResults(disparityImageLeft, tempFolder, 'stereoPixelPairsLeftLarge.csv', 16, False)

        # TODO: Many changes needed before RE images can be used here!
        #pixelPairsRightLarge = extractPixelPairsFromStereoResults(disparityImageRight, tempFolder, 'stereoPixelPairsRightLarge.csv', 16, False)

        pixelPairsLarge = os.path.join(tempFolder, 'stereoPixelPairsLarge.csv')
        if not os.path.exists(pixelPairsLarge):
            #TODO: Can't use RE pixel pairs without applying their local correction earlier!
            #cmd = 'cat < ' + pixelPairsLeftLarge + ' < ' + pixelPairsRightLarge + ' > ' + pixelPairsLarge
            cmd = 'cp ' + pixelPairsLeftLarge + ' ' + pixelPairsLarge
            print cmd
            os.system(cmd)
        else:
            print 'Skipping large pair merging extraction step'

        #print 'QUITTING EARLY'
        #return 0 # Don't forget to set the cropped file!


# TODO: Move this functionality to the double solver so it does not need to be hacked
        globalParamsFile  = sbaOutputPrefix + "-finalParamState-cropped.csv"
        # Compute the 3d coordinates for each pixel pair using the rotation and offset computed earlier
        largeGdcFile = os.path.join(tempFolder, 'gdcPointsLarge.csv')
        if True:#not os.path.exists(largeGdcFile):
            cmd = '/home/smcmich1/repo/lronacPipelineBuild/lronacAngleSolver --outputPath dummy.txt --gdcPointsOutPath ' + largeGdcFile + ' --matchingPixelsPath ' + pixelPairsLarge + ' ' + posOffsetCorrectedLeftPath + ' ' + posOffsetCorrectedStereoLeftPath + " --worldTransform --includePosition --initialOnly --initialValues " + globalParamsFile 
            print cmd
            os.system(cmd)
        else:
            print 'Skipping large GDC file creation step'

        # TODO: Why does rotation always move the points somewhere else?
        # Use pc-align to compare points to LOLA DEM, compute rotation and offset
        pcAlignOutputPrefix   = os.path.join(tempFolder, 'pcAlignOutput/dem')
        #largeGdcTransformedFile = os.path.joint(tempFolder, 'gdcPointsTransformedLarge.csv')
        #transformedPointsFile = os.path.join(tempFolder, 'pcAlignOutput-trans_source.csv')
        transformMatrixFile   = pcAlignOutputPrefix + '-inverse-transform.txt'
        if True:#not os.path.exists(transformMatrixFile):
            #cmd = 'pc_align --highest-accuracy --max-displacement 600 --datum D_MOON --max-num-reference-points 25000000 --save-transformed-source-points ' + options.lolaPath + ' ' + largeGdcFile + ' -o ' + pcAlignOutputPrefix + ' --compute-translation-only'
            cmd = 'pc_align --highest-accuracy --max-displacement 600 --datum D_MOON --save-inv-transformed-reference-points ' + largeGdcFile + ' ' + options.lolaPath + ' -o ' + pcAlignOutputPrefix + ' --compute-translation-only'
            print cmd
            os.system(cmd)
        else:
            print 'Skipping pc_align step'

        #print 'QUITTING EARLY'
        #return 0 

  #NOTE: Currently testing with identify transformation................................


        # Now go back and apply the pc_align computed transform to the left and right input image
        leftCkPath  = os.path.join(tempFolder, 'leftFinalCk.bc') #TODO: Do we need to specify these?
        leftSpkPath = os.path.join(tempFolder, 'leftFinalSpk.bsp')
        thisWorkDir = os.path.join(tempFolder, 'leftFullCorrection')
        applyNavTransform(posOffsetCorrectedLeftPath, options.outputPathLeft, transformMatrixFile, thisWorkDir, leftCkPath, leftSpkPath, false)

        tempRightPath = os.path.join(tempFolder, 'partial_corrected_RE.cub')
        rightCkPath   = os.path.join(tempFolder, 'rightFinalCk.bc') # Need these later to pass to internal angle correction function
        rightSpkPath  = os.path.join(tempFolder, 'rightFinalSpk.bsp')
        thisWorkDir   = os.path.join(tempFolder, 'rightFullCorrection/')
        applyNavTransform(posOffsetCorrectedRightPath, tempRightPath, transformMatrixFile, thisWorkDir, rightCkPath, rightSpkPath, false)


        # Do the same correction for the stereo-left and stereo-right images
        leftStereoCkPath  = os.path.join(tempFolder, 'leftStereoFinalCk.bc') #msopck can't handle the default kernel paths
        leftStereoSpkPath = os.path.join(tempFolder, 'leftStereoFinalSpk.bsp')
        thisWorkDir       = os.path.join(tempFolder, 'leftStereoFullCorrection')
        applyNavTransform(tempLeftStereoPath, options.outputPathStereoLeft, transformMatrixFile, thisWorkDir, leftStereoCkPath, leftStereoSpkPath, false)

        tempRightStereoPath2 = os.path.join(tempFolder, 'partial_corrected_stereo_RE.cub')
        rightStereoCkPath    = os.path.join(tempFolder, 'rightStereoFinalCk.bc') # Need these later to pass to internal angle correction function
        rightStereoSpkPath   = os.path.join(tempFolder, 'rightStereoFinalSpk.bsp')
        thisWorkDir          = os.path.join(tempFolder, 'rightStereoFullCorrection/')
        applyNavTransform(tempRightStereoPath, tempRightStereoPath2, transformMatrixFile, thisWorkDir, rightStereoCkPath, rightStereoSpkPath, false)

        # At this point the left images are hopefully in the correct position and we can apply the offset of the RE cameras

        # DEBUG: Check angle solver on stereo adjusted LE/RE images!
        checkAdjacentPairAlignment(options.outputPathStereoLeft, tempRightStereoPath2, tempFolder, 'pairGdcCheckMidStereo.csv', False)



        #print 'QUITTING EARLY'
        #return 0 

        # Apply local transforms to both pairs of images!

        # Apply the local rotation to the adjusted RE cube
        applyInterCameraPairRotation(options.outputPathLeft, tempRightPath, localRotationPath, options.outputPathRight, rightCkPath, rightSpkPath, False)

        # Apply the local rotation to the adjusted stereo RE cube
        applyInterCameraPairRotation(options.outputPathStereoLeft, tempRightStereoPath2, stereoRotationPath, options.outputPathStereoRight, rightStereoCkPath, rightStereoSpkPath, False)

        # DEBUG: Check angle solver on adjusted LE/RE images!
        checkAdjacentPairAlignment(options.outputPathLeft, options.outputPathRight, tempFolder, 'pairGdcCheckFinal.csv', False)

        # DEBUG: Check angle solver on stereo adjusted LE/RE images!
        checkAdjacentPairAlignment(options.outputPathStereoLeft, options.outputPathStereoRight, tempFolder, 'pairGdcCheckFinalStereo.csv', False)


        # Clean up temporary files
#        if not options.keep:
#            os.remove(tempTextPath)

      

        endTime = time.time()

        print "Finished stereo calibration process in " + str(endTime - startTime) + " seconds."
        return 0

    except Usage, err:
        print >>sys.stderr, err.msg
        return 2

if __name__ == "__main__":
    sys.exit(main())
