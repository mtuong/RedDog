#!/bin/env python

'''
RedDog V0.4.6 110414
====== 
Authors: David Edwards, Bernie Pope, Kat Holt

Description: 

This program implements a workflow pipeline for short read length
sequencing analysis, including the read mapping task, through to variant
detection, followed by analyses (SNPs only).

It uses Rubra (https://github.com/bjpop/rubra) based on the
Ruffus library.

It supports parallel evaluation of independent pipeline stages,
and can run stages on a cluster environment.

Note: for Illumina paired-end or single reads, or Ion Torrent single reads.
IMPORTANT: See pipeline_config.py for input options/requirements

Version History: See ReadMe.txt

License: none as yet...
'''
from ruffus import *
import os.path
import shutil
from pipe_utils import (getValue, getCover, isGenbank, isFasta)
from chrom_info import (chromInfoFasta, chromInfoGenbank)
import sys
import glob
from rubra.utils import pipeline_options
from rubra.utils import (runStageCheck, zeroFile, splitPath)

# determine the reference file,
# list of sequence files, and list of chromosmes.
reference = pipeline_options.reference

if isFasta(reference):
    refGenbank = False
    replicons = chromInfoFasta(reference)
elif isGenbank(reference):
    refGenbank = True
    replicons = chromInfoGenbank(reference)
else:
    print "\nReference not in GenBank or FASTA format"
    print "Pipeline Stopped: please check your reference\n"
    sys.exit()

if len(replicons)>1:
    for i in range(len(replicons)-1):
        for j in range (i+1, len(replicons)):
            if replicons[i][0] != replicons[j][0]:
                pass
            else:
                print "\nReference has replicons with non-unique names: " + replicons[i][0]
                print "Pipeline Stopped: please check your reference\n"
                sys.exit()

(refPrefix, refName, refExt) = splitPath(reference)
#add check for replicon names in reference not in name:int-int form
sequencePatterns = pipeline_options.sequences
runType = pipeline_options.runType
core_replicon = pipeline_options.core_replicon

if runType != "":
    if runType == "pangenome" or runType == "phylogeny":
        pass
    else:
        print "\nUnrecognised run type"
        print "Pipeline Stopped: please check 'runType' in the options file\n"
        sys.exit()
if runType == "":
    if len(replicons) > 100:
        runType = "pangenome"
    elif len(replicons) > 0:
        runType = "phylogeny"
if len(replicons) < 1:
    print "\nNo chromosomes found in reference"
    print "Pipeline Stopped: please check 'reference' in the options file\n"
    sys.exit()

repliconNames = []
longest_replicon_length = 0
for repliconName, repliconLength in replicons:
    repliconNames.append(repliconName)
    if int(repliconLength) > longest_replicon_length:
        longest_replicon_length = int(repliconLength)

if runType == "pangenome":
    if core_replicon == "":
        for repliconName, repliconLength in replicons:
            if int(repliconLength) == longest_replicon_length:
                core_replicon = repliconName
    core_replicons = core_replicon.split(', ')

sequences = []
if type(sequencePatterns) == list:
    for pattern in sequencePatterns:
        sequences += glob.glob(pattern)
else:
    sequences = glob.glob(sequencePatterns)

if sequences == []:
    if sequencePatterns == "":
        print "\nNo mapping - analysis only"
        print "Pipeline Stopped: Not Yet Available\n"
        sys.exit()
    else:
        print "\nNo matching sequences found"
        print "Pipeline Stopped: please check 'sequences' in options\n"
        sys.exit()

readType = pipeline_options.readType
if readType == 'IT' or readType == 'PE' or readType == 'SE':
    pass
else:
    print "\nUnrecognised read type"
    print "Pipeline Stopped: please check 'readType' in options\n"
    sys.exit()

mapping_out = ""
if pipeline_options.mapping == "":
    mapping = 'bowtie'
else:
    mapping = pipeline_options.mapping

if mapping == 'bwa' and readType == 'SE':
    mapping_out = 'BWA V0.6.2 samse'
elif mapping == 'bwa' and readType == 'PE':
    mapping_out = 'BWA V0.6.2 sampe'
elif mapping == 'bowtie':
    mapping_out = 'Bowtie2 V2.1.0'
else:
    print "\nUnrecognised mapping option"
    print "Pipeline Stopped: please check 'mapping' in the options file\n"
    sys.exit()

sequence_list = []
for sequence in sequences:
    (prefix, name, ext) = splitPath(sequence)
    if readType == "IT":
        sequence_list.append(name[:-16])
    elif readType == "PE":
        if name.find('_1.f') != -1:
            sequence_list.append(name[:-8])
    else:
        sequence_list.append(name[:-6])

if readType == 'PE':
    missing_pairs = []
    for seqName in sequence_list:
        test_1 = False
        test_2 = False
        for sequence in sequences:
            if sequence.find(seqName+'_1.f') != -1:
                test_1 = True
            if sequence.find(seqName+'_2.f') != -1:
                test_2 = True
        if test_1 == False or test_2 == False:
            missing_pairs.append(seqName)
    if missing_pairs != []:
        print "\nNot all sequence sets have pairs:"
        print missing_pairs
        print "Pipeline Stopped: please fix sequence pairs\n"
        sys.exit()

if pipeline_options.bowtie_map_type == "":
    bowtie_map_type = '--sensitive-local'
else:
    bowtie_map_type = pipeline_options.bowtie_map_type
if (bowtie_map_type == "--very-fast" or
    bowtie_map_type == "--fast" or
    bowtie_map_type == "--sensitive" or
    bowtie_map_type == "--very-sensitive" or
    bowtie_map_type == "--very-fast-local" or
    bowtie_map_type == "--fast-local" or
    bowtie_map_type == "--sensitive-local" or
    bowtie_map_type == "--very-sensitive-local"):
    pass        
else:
    print "\nUnrecogised Bowtie2 mapping option"
    print "Pipeline Stopped: please check 'bowtie_map_type' in the options file\n"
    sys.exit()

minDepth = pipeline_options.minimum_depth
coverFail = pipeline_options.cover_fail 
depthFail = pipeline_options.depth_fail 
mappedFail = pipeline_options.mapped_fail
sdOutgroupMultiplier = pipeline_options.sd_out

check_reads_mapped = pipeline_options.check_reads_mapped
if check_reads_mapped == "":
    for repliconName, repliconLength in replicons:
        if int(repliconLength) == longest_replicon_length:
            check_reads_mapped = repliconName

outPrefix = pipeline_options.output
if outPrefix == "":
    print "\nNo Output folder given"
    print "Pipeline Stopped: please check 'output' the options file\n"
    sys.exit()
if outPrefix[-1] != '/':
    outPrefix += '/'

outMerge = pipeline_options.out_merge_target
if outMerge != '':
    if outMerge[-1] != '/':
        outMerge += '/'
if outPrefix == outMerge:
    print "\nOutput folder and out_merge_target for run are the same"
    print "Pipeline Stopped: please check 'output' and 'out_merge_target' in the options file\n"
    sys.exit()

replaceReads = pipeline_options.replaceReads
replaceReads = '"'+replaceReads+'"'
outTempPrefix = outPrefix + 'temp/'
outSuccessPrefix = outTempPrefix + 'success/'
outBamPrefix = outPrefix + 'bam/'
outVcfPrefix = outPrefix + 'vcf/'
if outMerge != "":
    outMergeBam = outMerge + 'bam/'
    outMergeVcf = outMerge + 'vcf/'

full_sequence_list = []
if outMerge == '':
    for item in sequence_list:
        full_sequence_list.append(item)
else:
    for item in sequence_list:
        full_sequence_list.append(item)
    try:
        sequence_list_file = open((outMerge + 'sequence_list.txt') , "r")
    except:
        print "\nNo sequence list found"
        print "Pipeline Stopped: please generate new 'sequence_list.txt' file\n"
        sys.exit()
    for line in sequence_list_file:
        full_sequence_list.append(line[:-1])

#Phew! Now that's all set up, we can begin...
#but first, output run conditions to user and get confirmation to run
print "\nRedDog V0.4.5.2 - " + runType + " run\n"
print "Mapping: " + mapping_out
if mapping == 'bowtie':
    print "Preset Option: " + bowtie_map_type
if refGenbank == False:
    ref_string = 'FASTA'
else:
    ref_string = 'GenBank'
print str(len(replicons)) + " replicon(s) in " + ref_string + " reference " + refName
if runType != '':
    if runType == 'phylogeny':
        number_string = str(len(replicons))
    else:
        number_string = str(len(core_replicons))
    print number_string + " replicon(s) to be reported"
number_string = str(len(sequence_list))
if readType == 'PE':
    print number_string + " sequence pair(s) to be mapped"
else:
    print number_string + " sequence(s) to be mapped"

print "\nOutput folder:"
print outPrefix
if outMerge != '':
    print "Remember: this output folder will be deleted at the end of the run\n"
    print "Merge new sets with the following folder ('out_merge_target'):"
    print outMerge

start_run = False
start_count = 0
while start_run == False:
    keyboard_entry = raw_input('\nStart Pipeline? (y/n) ')
    if keyboard_entry == 'y' or keyboard_entry == 'Y' or keyboard_entry == 'yes' or keyboard_entry == 'Yes' or keyboard_entry == 'YES':
        start_run = True
    elif keyboard_entry == 'n' or keyboard_entry == 'N' or keyboard_entry == 'no' or keyboard_entry == 'No' or keyboard_entry == 'NO':
        print "\nPipeline Stopped: user request\n"
        sys.exit()
    else:
        start_count +=1
        if start_count >= 3:
            print "\nPipeline Stopped: too many tries\n"
            sys.exit()
        else:
            print "Please enter 'y' (yes) or 'n' (no)"

print "\nStarting pipeline..."

# Create temp and other output subfolders
@files(input==None, outSuccessPrefix + "dir.makeDir.Success")
def makeDir(input, flagFile):
    runStageCheck('makeDir', flagFile, outSuccessPrefix, outBamPrefix, outVcfPrefix)

if refGenbank == False:
    # Copy reference to outTemp
    newReference = outTempPrefix + refName + refExt
    @follows(makeDir)
    @files(reference, [newReference, outSuccessPrefix + refName + '.copyRef.Success'])
    def copyRef(reference, outputs):
        _output, flagFile = outputs
        runStageCheck('copyRef', flagFile, reference, outTempPrefix)
    reference = newReference

    # Index copy of reference for SNP calling by samtools
    @follows(copyRef)
    @files(reference, [reference + '.fai', outSuccessPrefix + refName + '.indexRef.Success'])
    def indexRef(reference, outputs):
        _output, flagFile = outputs
        runStageCheck('indexRef', flagFile, reference)

    if mapping == 'bowtie':
        # Index the reference file for bowtie2
        @follows(copyRef)
        @files(reference, [outTempPrefix + refName + '.1.bt2', outSuccessPrefix + refName + '.buildBowtieIndex.Success'])
        def buildBowtieIndex(reference, outputs):
            output, flagFile = outputs
            base = output[:-6]
            runStageCheck('buildBowtieIndex', flagFile, reference, base)
    else:
        # Index the reference file for bwa
        @follows(copyRef)
        @files(reference, [reference + '.bwt', outSuccessPrefix + refName + '.buildBWAIndex.Success'])
        def buildBWAIndex(reference, outputs):
            _output, flagFile = outputs
            runStageCheck('buildBWAIndex', flagFile, reference)

else:
    #make a fasta version of the reference for mapping
    genbank = reference
    reference = outTempPrefix + refName + ".fasta"
    @follows(makeDir)
    @files(genbank, [reference, outSuccessPrefix + refName + '.makeFasta.Success'])
    def makeRef(genbank, outputs):
        output, flagFile = outputs
        runStageCheck('makeRef', flagFile, genbank, output)

    # Index constructed reference for SNP calling by samtools
    @follows(makeRef)
    @files(reference, [reference + '.fai', outSuccessPrefix + refName + '.indexRef.Success'])
    def indexRef(reference, outputs):
        _output, flagFile = outputs
        runStageCheck('indexRef', flagFile, reference)

    if mapping == 'bowtie':
        # Index the reference file for bowtie2
        @follows(makeRef)
        @files(reference, [outTempPrefix + refName + '.1.bt2', outSuccessPrefix + refName + '.buildBowtieIndex.Success'])
        def buildBowtieIndex(reference, outputs):
            output, flagFile = outputs
            base = output[:-6]
            runStageCheck('buildBowtieIndex', flagFile, reference, base)
    else:
        # Index the reference file for bwa
        @follows(makeRef)
        @files(reference, [reference + '.bwt', outSuccessPrefix + refName + '.buildBWAIndex.Success'])
        def buildBWAIndex(reference, outputs):
            _output, flagFile = outputs
            runStageCheck('buildBWAIndex', flagFile, reference)

if mapping == 'bowtie':
    if readType == "PE":
        #align reads with Bowtie2 to sorted bam
        input = r'(.*)\/(.+)_1\.fastq.gz'
        extraInput = [r'\1/\2_2.fastq.gz']
        @follows(buildBowtieIndex)
        @transform(sequences, regex(input), add_inputs(extraInput), [outTempPrefix + r'\2.bam', outSuccessPrefix + r'\2.alignBowtiePE.Success'])
        def alignBowtiePE(inputs, outputs):
            output, flagFile = outputs
            (prefix, name, ext) = splitPath(output)
            out = prefix + '/' + name
            seq1, [seq2] = inputs
            base = outTempPrefix + refName
            runStageCheck('alignBowtiePE', flagFile, bowtie_map_type, base, seq1, seq2, out)

        # Index sorted BAM alignments using samtools
        @transform(alignBowtiePE, regex(r"(.*)\/(.+).bam"), [r'\1/\2.bam.bai', outSuccessPrefix + r'\2.indexBam.Success'])
        def indexBam(inputs, outputs):
            output, flagFile = outputs
            bamFile, _success = inputs
            runStageCheck('indexBam', flagFile, bamFile)

        #get bam stats by replicon
        @follows(indexBam)
        @transform(alignBowtiePE, regex(r"(.*)\/(.+).bam"), [outTempPrefix + r"\2_samStats.txt", outSuccessPrefix + r'\2.getSamStats.Success'])
        def getSamStats(inputs, outputs):
            output, flagFile = outputs
            bamFile, _success = inputs
            runStageCheck('getSamStats', flagFile, bamFile, output)

        #filter unmapped reads
        @follows(indexBam)
        @transform(alignBowtiePE, regex(r"(.*)\/(.+).bam"), [outBamPrefix + r'\2.bam', outSuccessPrefix + r'\2.filterUnmapped.Success'])
        def filterUnmapped(inputs, outputs):
            output, flagFile = outputs
            bamFile, _success = inputs
            (prefix, name, ext) = splitPath(output)
            out = prefix + '/' + name
            runStageCheck('filterUnmapped', flagFile, bamFile, out)

    else:
        if readType=="SE":
            #align reads with Bowtie2 to sorted bam
            @follows(buildBowtieIndex)
            @transform(sequences, regex(r"(.*)\/(.+).fastq.gz"), [outTempPrefix + r'\2.bam', outSuccessPrefix + r'\2.alignBowtie.Success'])
            def alignBowtie(input, outputs):
                output, flagFile = outputs
                (prefix, name, ext) = splitPath(output)
                out = prefix + '/' + name
                base = outTempPrefix + refName
                runStageCheck('alignBowtie', flagFile, bowtie_map_type, base, input, out)
     
        else: #readType == "IT"
            #align reads with Bowtie2 to sorted bam
            @follows(buildBowtieIndex)
            @transform(sequences, regex(r"(.*)\/(.+)_in.iontor.fastq.gz"), [outTempPrefix + r'\2.bam', outSuccessPrefix + r'\2.alignBowtie.Success'])
            def alignBowtie(input, outputs):
                output, flagFile = outputs
                (prefix, name, ext) = splitPath(output)
                out = prefix + '/' + name
                base = outTempPrefix + refName
                runStageCheck('alignBowtie', flagFile, bowtie_map_type, base, input, out)

        # Index sorted BAM alignments using samtools
        @transform(alignBowtie, regex(r"(.*)\/(.+).bam"), [r'\1/\2.bam.bai', outSuccessPrefix + r'\2.indexBam.Success'])
        def indexBam(inputs, outputs):
            output, flagFile = outputs
            bamFile, _success = inputs
            runStageCheck('indexBam', flagFile, bamFile)

        #get bam stats by replicon
        @follows(indexBam)
        @transform(alignBowtie, regex(r"(.*)\/(.+).bam"), [outTempPrefix + r"\2_samStats.txt", outSuccessPrefix + r'\2.getSamStats.Success'])
        def getSamStats(inputs, outputs):
            output, flagFile = outputs
            bamFile, _success = inputs
            runStageCheck('getSamStats', flagFile, bamFile, output)

        #filter unmapped reads
        @follows(indexBam)
        @transform(alignBowtie, regex(r"(.*)\/(.+).bam"), [outBamPrefix + r'\2.bam', outSuccessPrefix + r'\2.filterUnmapped.Success'])
        def filterUnmapped(inputs, outputs):
            output, flagFile = outputs
            bamFile, _success = inputs
            (prefix, name, ext) = splitPath(output)
            out = prefix + '/' + name
            runStageCheck('filterUnmapped', flagFile, bamFile, out)

else: # mapping = 'BWA'
    # Align sequence reads to the reference genome.
    @follows(buildBWAIndex)
    @transform(sequences, regex(r"(.*)\/(.+).fastq.gz"), [outTempPrefix + r"\2.sai", outSuccessPrefix + r"\2.alignSequence.Success"])
    def alignSequence(sequence, outputs):
        output, flagFile = outputs
        runStageCheck('alignSequence', flagFile, reference, sequence, output)

    if readType == "PE":
        #align reads with BWA to sorted bam
        input = r'(.*)\/(.+)_1\.sai'
        extraInput = [r'\1/\2_2.sai']
        @transform(alignSequence, regex(input), add_inputs(extraInput), [outTempPrefix + r'\2.bam', outSuccessPrefix + r'\2.alignBWAPE.Success'])
        def alignBWAPE(inputs, outputs):
            output, flagFile = outputs
            [align1, _success], [align2] = inputs
            (prefix, name, ext) = splitPath(align1)
            seqPrefix = ""
            for sequence in sequences:
                if sequence.find(name) != -1 and seqPrefix == "":
                    (seqPrefix, seqName, seqExt) = splitPath(sequence)
            name = seqPrefix + "/" + name[:-2]
            seq1 = name + '_1.fastq.gz'
            seq2 = name + '_2.fastq.gz'
            (prefix, name, ext) = splitPath(output)
            out = prefix + '/' + name
            runStageCheck('alignBWAPE', flagFile, reference, align1, align2, seq1, seq2, out)

        # Index sorted BAM alignments using samtools
        @transform(alignBWAPE, regex(r"(.*)\/(.+).bam"), [r'\1/\2.bam.bai', outSuccessPrefix + r'\2.indexBam.Success'])
        def indexBam(inputs, outputs):
            output, flagFile = outputs
            bamFile, _success = inputs
            runStageCheck('indexBam', flagFile, bamFile)

        #get bam stats by replicon
        @follows(indexBam)
        @transform(alignBWAPE, regex(r"(.*)\/(.+).bam"), [outTempPrefix + r"\2_samStats.txt", outSuccessPrefix + r'\2.getSamStats.Success'])
        def getSamStats(inputs, outputs):
            output, flagFile = outputs
            bamFile, _success = inputs
            runStageCheck('getSamStats', flagFile, bamFile, output)

        #filter unmapped reads
        @follows(indexBam)
        @transform(alignBWAPE, regex(r"(.*)\/(.+).bam"), [outBamPrefix + r'\2.bam', outSuccessPrefix + r'\2.filterUnmapped.Success'])
        def filterUnmapped(inputs, outputs):
            output, flagFile = outputs
            bamFile, _success = inputs
            (prefix, name, ext) = splitPath(output)
            out = prefix + '/' + name
            runStageCheck('filterUnmapped', flagFile, bamFile, out)

    else:
        #align reads with BWA to sorted bam
        @follows(buildBWAIndex)
        @transform(alignSequence, regex(r"(.*)\/(.+).sai"), [outTempPrefix + r'\2.bam', outSuccessPrefix + r'\2.alignBWASE.Success'])
        def alignBWASE(inputs, outputs):
            output, flagFile = outputs
            align, _success = inputs
            (prefix, name, ext) = splitPath(align)
            seqPrefix = ""
            for sequence in sequences:
                if sequence.find(name) != -1 and seqPrefix == "":
                    (seqPrefix, seqName, seqExt) = splitPath(sequence)
            seq = seqPrefix + "/" + name + '.fastq.gz'
            (prefix, name, ext) = splitPath(output)
            out = prefix + '/' + name
            runStageCheck('alignBWASE', flagFile, reference, align, seq, out)

        # Index sorted BAM alignments using samtools
        @transform(alignBWASE, regex(r"(.*)\/(.+).bam"), [r'\1/\2.bam.bai', outSuccessPrefix + r'\2.indexBam.Success'])
        def indexBam(inputs, outputs):
            output, flagFile = outputs
            bamFile, _success = inputs
            runStageCheck('indexBam', flagFile, bamFile)

        #get bam stats by replicon
        @follows(indexBam)
        @transform(alignBWASE, regex(r"(.*)\/(.+).bam"), [outTempPrefix + r"\2_samStats.txt", outSuccessPrefix + r'\2.getSamStats.Success'])
        def getSamStats(inputs, outputs):
            output, flagFile = outputs
            bamFile, _success = inputs
            runStageCheck('getSamStats', flagFile, bamFile, output)

        #filter unmapped reads
        @follows(indexBam)
        @transform(alignBWASE, regex(r"(.*)\/(.+).bam"), [outBamPrefix + r'\2.bam', outSuccessPrefix + r'\2.filterUnmapped.Success'])
        def filterUnmapped(inputs, outputs):
            output, flagFile = outputs
            bamFile, _success = inputs
            (prefix, name, ext) = splitPath(output)
            out = prefix + '/' + name
            runStageCheck('filterUnmapped', flagFile, bamFile, out)

# Index sorted BAM alignments using samtools
@transform(filterUnmapped, regex(r"(.*)\/(.+).bam"), [r'\1/\2.bam.bai', outSuccessPrefix + r'\2.indexFilteredBam.Success'])
def indexFilteredBam(inputs, outputs):
    output, flagFile = outputs
    bamFile, _success = inputs
    runStageCheck('indexBam', flagFile, bamFile)

# get consensus sequence from bam
@follows(indexFilteredBam)
@follows(indexRef)
@transform(filterUnmapped, regex(r"(.*)\/(.+).bam"), [outTempPrefix + r"\2_cns.fq", outSuccessPrefix + r"\2.getConsensus.Success"])
def getConsensus(inputs, outputs):
    output, flagFile = outputs
    bamFile, _success = inputs
    runStageCheck('getConsensus', flagFile, reference, bamFile, output)

# Get coverage from BAM
@follows(indexFilteredBam)
@follows(indexRef)
@transform(filterUnmapped, regex(r"(.*)\/(.+).bam"), [outTempPrefix + r"\2_coverage.txt", outSuccessPrefix + r"\2.getCoverage.Success"])
def getCoverage(inputs, outputs):
    output, flagFile = outputs
    bamFile, _success = inputs
    runStageCheck('getCoverage', flagFile, bamFile, output)

# Get coverage by replicon
@transform(getCoverage, regex(r"(.*)\/(.+)_coverage.txt"), [r'\1/\2_rep_cover.txt', outSuccessPrefix + r'\2.getCoverByRep.Success'])
def getCoverByRep(inputs, outputs):
    output, flagFile = outputs
    coverageFile, _success = inputs
    runStageCheck('getCoverByRep', flagFile, reference, coverageFile, output)

if runType == "pangenome":
    #create inputs for callRepSNPs
    def snpsByCoreReplicons():
        for repliconName in core_replicons:
            for seqName in sequence_list:
                sortedBam = outBamPrefix + seqName + '.bam'
                output = outTempPrefix + seqName + '_' + repliconName + '_raw.bcf'
                flagFile = outSuccessPrefix + seqName + '_' + repliconName + '.callRepSNPs.Success'
                yield([sortedBam, output, repliconName, flagFile])

    # Call SNPs for core replicon(s)
    @follows(indexFilteredBam)
    @follows(indexRef)
    @files(snpsByCoreReplicons)
    def callRepSNPs(sortedBam, output, repliconName, flagFile):
        runStageCheck('callRepSNPs', flagFile, reference, sortedBam, repliconName, output)

    #create inputs for filter variants on Q30
    def q30FilterByCoreReplicons():
        for repliconName in core_replicons:
            for seqName in sequence_list:
                rawBCF = outTempPrefix + seqName + '_' + repliconName + '_raw.bcf'
                coverFile = outTempPrefix + seqName + '_rep_cover.txt'                        
                output = outTempPrefix + seqName + '_' + repliconName + '_raw.vcf'
                flagFile = outSuccessPrefix + seqName + '_' + repliconName + '.q30VarFilter.Success'
                yield([rawBCF, output, coverFile, repliconName, flagFile])
    
    # Filter variants on Q30
    @follows(getCoverByRep)
    @follows(callRepSNPs)
    @files(q30FilterByCoreReplicons)
    def q30VarFilter(rawBCF, output, coverFile, repliconName, flagFile):
        cover = getCover(coverFile, repliconName)
        runStageCheck('q30VarFilter', flagFile, rawBCF, minDepth, cover, output)

    # Filter out simple hets
    @transform(q30VarFilter, regex(r"(.*)\/(.+)_raw.vcf"), [outVcfPrefix + r"\2_q30.vcf", outSuccessPrefix + r"\2.finalFilter.Success"])
    def finalFilter(vcfFile, outputs):
        output, flagFile = outputs
        runStageCheck('finalFilter', flagFile, vcfFile, output)

else: # runType == "phylogeny"
    #create inputs for callRepSNPs
    def snpsByReplicons():
        for repliconName in replicons:
            for seqName in sequence_list:
                sortedBam = outTempPrefix + seqName + '.bam'
                output = outTempPrefix + seqName + '_' + repliconName[0] + '_raw.bcf'
                flagFile = outSuccessPrefix + seqName + '_' + repliconName[0] + '.callRepSNPs.Success'
                replicon = repliconName[0]
                yield([sortedBam, output, replicon, flagFile])

    # Call SNPs for all replicon(s)
    @follows(indexFilteredBam)
    @follows(indexRef)
    @files(snpsByReplicons)
    def callRepSNPs(sortedBam, output, replicon, flagFile):
        runStageCheck('callRepSNPs', flagFile, reference, sortedBam, replicon, output)

    #create inputs for filter variants on Q30
    def q30FilterByReplicons():
        for repliconName in replicons:
            for seqName in sequence_list:
                rawBCF = outTempPrefix + seqName + '_' + repliconName[0] + '_raw.bcf'
                coverFile = outTempPrefix + seqName + '_rep_cover.txt'    
                output = outTempPrefix + seqName + '_' + repliconName[0] + '_raw.vcf'
                flagFile = outSuccessPrefix + seqName + '_' + repliconName[0] + '.q30VarFilter.Success'
                replicon = repliconName[0]
                yield([rawBCF, output, coverFile, replicon, flagFile])
    
    # Filter variants on Q30
    @follows(getCoverByRep)
    @follows(callRepSNPs)
    @files(q30FilterByReplicons)
    def q30VarFilter(rawBCF, output, coverFile, replicon, flagFile):
        cover = getCover(coverFile, replicon)
        runStageCheck('q30VarFilter', flagFile, rawBCF, minDepth, cover, output)

    # Filter out simple hets
    @transform(q30VarFilter, regex(r"(.*)\/(.+)_raw.vcf"), [outVcfPrefix + r"\2_q30.vcf", outSuccessPrefix + r"\2.finalFilter.Success"])
    def finalFilter(vcfFile, outputs):
        output, flagFile = outputs
        runStageCheck('finalFilter', flagFile, vcfFile, output)

# Get the vcf statistics
@transform(finalFilter, regex(r"(.*)\/(.+)_q30.vcf"), [outTempPrefix + r"\2_vcf.txt", outSuccessPrefix + r"\2.getVcfStats.Success"])
def getVcfStats(inputs, outputs):
    output, flagFile = outputs
    vcfFile, _success = inputs
    runStageCheck('getVcfStats', flagFile, vcfFile, output)

# Derive run statistics - first, the 'all statistics' data
@follows(getSamStats)
@transform(getCoverByRep, regex(r"(.*)\/(.+)_rep_cover.txt"), [r'\1/\2_AllStats.txt', outSuccessPrefix + r'\2.deriveAllStats.Success'])
def deriveAllStats(inputs, outputs):
    output, flagFile = outputs
    coverFile, _success = inputs
    runStageCheck('deriveAllStats', flagFile, coverFile)

# Collate run statistics into tab-delimited file
# and add header to the statistics file
# example rep cover file is to establish replicon order in the header (order from reference)
# also provides a user-friendly version of the all stats file with isolates as the header (for spreadsheets) 
@merge(deriveAllStats, [outPrefix + refName + "_AllStats.txt", outSuccessPrefix + refName + ".collateAllStats.Success"])
def collateAllStats(inputs, outputs):
    output, flagFile = outputs
    example_name = sequence_list[0]
    exampleRepCover = outTempPrefix + example_name + "_rep_cover.txt"
    runStageCheck('collateAllStats', flagFile, refName, exampleRepCover)

if runType == "pangenome":
    # Derive run statistics - second, the statistics for each replicon (largest or user-defined list)
    def statsByCoreRep():
        for repliconName in core_replicons:
            for seqName in sequence_list:
                coverFile = outTempPrefix + seqName + '_rep_cover.txt'
                output = outTempPrefix + seqName + '_' + repliconName + '_RepStats.txt'
                flagFile = outSuccessPrefix + seqName + '_' + repliconName + '.deriveRepStats.Success'
                yield([coverFile, output, repliconName, depthFail, coverFail, flagFile])

    @follows(getVcfStats)
    @follows(getSamStats)
    @follows(getCoverByRep)
    @files(statsByCoreRep)
    def deriveRepStats(coverFile, output, repliconName, depthFail, coverFail, flagFile):
        runStageCheck('deriveRepStats', flagFile, coverFile, repliconName, depthFail, coverFail, runType, mappedFail, check_reads_mapped)

    def inputByCoreRep():
        for repliconName in core_replicons:
            example_name = sequence_list[0]
            exampleRepCover = outTempPrefix + example_name + "_rep_cover.txt"
            output = outPrefix + refName + '_' + repliconName + '_RepStats.txt'
            flagFile = outSuccessPrefix + refName + '_' + repliconName + '.collateRepStats.Success'
            yield([input==None, output, refName, exampleRepCover, repliconName, flagFile])

    @follows(deriveRepStats)
    @files(inputByCoreRep)
    def collateRepStats(input, output, refName, exampleRepCover, repliconName, flagFile):
        runStageCheck('collateRepStats', flagFile, refName, exampleRepCover, repliconName, sdOutgroupMultiplier, runType)

else: #runType == "phylogeny":
    # Derive run statistics - second, the statistics for each replicon (largest or user-defined list)
    def statsByRep():
        for repliconName in replicons:
            for seqName in sequence_list:
                coverFile = outTempPrefix + seqName + '_rep_cover.txt'
                output = outTempPrefix + seqName + '_' + repliconName[0] + '_RepStats.txt'
                flagFile = outSuccessPrefix + seqName + '_' + repliconName[0] + '.deriveRepStats.Success'
                replicon = repliconName[0]
                yield([coverFile, output, replicon, depthFail, coverFail, flagFile])

    @follows(getVcfStats)
    @follows(getSamStats)
    @follows(getCoverByRep)
    @files(statsByRep)
    def deriveRepStats(coverFile, output, replicon, depthFail, coverFail, flagFile):
        runStageCheck('deriveRepStats', flagFile, coverFile, replicon, depthFail, coverFail, runType, mappedFail, check_reads_mapped)

    def inputByRep():
        for repliconName in replicons:
            example_name = sequence_list[0]
            exampleRepCover = outTempPrefix + example_name + "_rep_cover.txt"
            output = outPrefix + refName + '_' + repliconName[0] + '_RepStats.txt'
            flagFile = outSuccessPrefix + refName + '_' + repliconName[0] + '.collateRepStats.Success'
            replicon = repliconName[0]
            yield([input==None, output, refName, exampleRepCover, replicon, flagFile])

    @follows(deriveRepStats)
    @files(inputByRep)
    def collateRepStats(input, output, refName, exampleRepCover, replicon, flagFile):
        runStageCheck('collateRepStats', flagFile, refName, exampleRepCover, replicon, sdOutgroupMultiplier, runType)

if outMerge != "":
    # Merge bams and vcfs to correct output merge directory
    @follows(collateAllStats)
    @follows(collateRepStats)
    @files(input==None, outSuccessPrefix + 'mergeOutputs.Success')
    def mergeOutputs(input, flagFile):
        inputBam = outBamPrefix + '*.bam'
        inputIndex = outBamPrefix + '*.bai'
        inputVcf = outVcfPrefix + '*.vcf' 
        runStageCheck('mergeOutputs', flagFile, inputBam, outMergeBam, inputIndex, outMergeBam, inputVcf, outMergeVcf)
 
    # Merge AllStats.txt files <- need to add 'user' version when merging
    @follows(mergeOutputs)
    @transform(collateAllStats, regex(r"(.*)\/(.+)_AllStats.txt"), [outMerge + r"\2_AllStats.txt", outSuccessPrefix + r"\2.mergeAllStats.Success"])
    def mergeAllStats(inputs, outputs):
        input, _success = inputs
        output, flagFile = outputs
        runStageCheck('mergeAllStats', flagFile, input, outMerge)

    # Merge RepStats.txt files
    @follows(mergeOutputs)
    @transform(collateRepStats, regex(r"(.*)\/(.+)_RepStats.txt"), [outMerge + r"\2_RepStats.txt", outSuccessPrefix + r"\2.mergeRepStats.Success"])
    def mergeRepStats(input, outputs):
        output, flagFile = outputs
        runStageCheck('mergeRepStats', flagFile, input, sdOutgroupMultiplier, replaceReads, outMerge, runType)

#    if mergeReads == "":
    if runType == "phylogeny":
        # Start of phylogeny analysis
        def snpListByRep():
            for repliconName in replicons:
                input  = outMerge + refName + '_' + repliconName[0] + '_RepStats.txt'
                output = outTempPrefix + refName + '_' + repliconName[0] + '_SNPList.txt'
                flagFile = outSuccessPrefix + refName + '_' + repliconName[0] + '.getRepSNPList.Success'
                replicon = repliconName[0]
                yield([input, output, replicon, flagFile])

        # Get unique SNP list for new set using stats file for each replicon
        @follows(mergeRepStats)
        @follows(mergeAllStats)
        @files(snpListByRep)
        def getRepSNPList(input, output, replicon, flagFile):
            runStageCheck('getRepSNPList', flagFile, input, replicon, output)

    else: #runType == "pangenome":
        # Start of pangenome analysis
        def snpListByCoreRep():
            for repliconName in core_replicons:
                input  = outMerge + refName + '_' + repliconName + '_RepStats.txt'
                output = outTempPrefix + refName + '_' + repliconName + '_SNPList.txt'
                flagFile = outSuccessPrefix + refName + '_' + repliconName + '.getRepSNPList.Success'
                replicon = repliconName
                yield([input, output, replicon, flagFile])

        # Get unique SNP list for new set using stats file for each replicon
        @follows(mergeRepStats)
        @follows(mergeAllStats)
        @files(snpListByCoreRep)
        def getRepSNPList(input, output, replicon, flagFile):
            runStageCheck('getRepSNPList', flagFile, input, replicon, output)

else:
    if runType == "phylogeny":
        # Start of new run phylogey analysis
        def snpListByRep():
            for repliconName in replicons:
                input  = outPrefix + refName + '_' + repliconName[0] + '_RepStats.txt'
                output = outTempPrefix + refName + '_' + repliconName[0] + '_SNPList.txt'
                flagFile = outSuccessPrefix + refName + '_' + repliconName[0] + '.getRepSNPList.Success'
                replicon = repliconName[0]
                yield([input, output, replicon, flagFile])

        # Get unique SNP list for new set using stats file for each replicon
        @follows(collateRepStats)
        @follows(collateAllStats)
        @files(snpListByRep)
        def getRepSNPList(input, output, replicon, flagFile):
            runStageCheck('getRepSNPList', flagFile, input, replicon, output)

    else: #runType == "pangenome":
        # Start of new run pangenome analysis
        def snpListByCoreRep():
            for repliconName in core_replicons:
                input  = outPrefix + refName + '_' + repliconName + '_RepStats.txt'
                output = outTempPrefix + refName + '_' + repliconName + '_SNPList.txt'
                flagFile = outSuccessPrefix + refName + '_' + repliconName + '.getRepSNPList.Success'
                replicon = repliconName
                yield([input, output, replicon, flagFile])

        # Get unique SNP list for new set using stats file for each replicon
        @follows(collateRepStats)
        @follows(collateAllStats)
        @files(snpListByCoreRep)
        def getRepSNPList(input, output, replicon, flagFile):
            runStageCheck('getRepSNPList', flagFile, input, replicon, output)

if refGenbank == True:
    if outMerge != "":
        bamPatterns = outMergeBam + '*.bam'
        bams = []
        if type(bamPatterns) == list:
            for pattern in bamPatterns:
                bams.append(glob.glob(pattern))
        else:
            bams = glob.glob(bamPatterns)        

        # generate data for the gene cover and depth matrices
        @transform(getCoverage, regex(r"(.*)\/(.+)_coverage.txt"), [outTempPrefix + r'\2_CoverDepthMatrix.txt', outSuccessPrefix + r'\2.deriveAllRepGeneCover.Success'])
        def deriveAllRepGeneCover(inputs, outputs):
            output, flagFile = outputs
            input, _success = inputs
            runStageCheck('deriveAllRepGeneCover', flagFile, outTempPrefix, genbank, input)

        # merge the data with the 'old' gene cover and depth matrices
        @merge(deriveAllRepGeneCover, [outMerge + refName + "_CoverMatrix.csv", outSuccessPrefix + refName + "_CoverMatrix.mergeAllRepGeneCover.Success"])
        def mergeAllRepGeneCover(inputs, outputs):
            output, flagFile = outputs
            runStageCheck('mergeAllRepGeneCover', flagFile, outTempPrefix, outMerge, refName)

        # parse gene cover (and depth - to come) matrices to summarise gene content
        @transform(mergeAllRepGeneCover, regex(r"(.*)\/(.+)_CoverMatrix.csv"), [outMerge + r"\2_GeneSummary.csv", outSuccessPrefix + r"\2_alleles.parseGeneContent.Success"])
        def parseGeneContent(inputs, outputs):
            output, flagFile = outputs
            (prefix, name, ext) = splitPath(output)
            output2 = prefix + "/" + name[:-11] + "PresenceAbsence.csv"
            input, _success = inputs
            runStageCheck('parseGeneContent', flagFile, input, output, output2)

        # get consensus sequences for merged set
        @follows(getRepSNPList)
        @transform(bams, regex(r"(.*)\/(.+).bam"), [outTempPrefix + r"\2_cns.fq", outSuccessPrefix + r"\2.getMergeConsensus.Success"])
        def getMergeConsensus(input, outputs):
            output, flagFile = outputs
            runStageCheck('getConsensus', flagFile, reference, input, output)

        if runType == 'pangenome':
            # generate the allele matrix entry for each isolate for each replicon
            def matrixEntryByCoreRep():
                for isolate in full_sequence_list:
                    for repliconName in core_replicons:
                        input = outTempPrefix + refName + '_' + repliconName + '_SNPList.txt'
                        output  = outTempPrefix + refName + '_' + repliconName + '_' + isolate + '_alleles.txt'
                        flagFile = outSuccessPrefix + refName + '_' + repliconName + '_' + isolate + '.deriveRepAlleleMatrix.Success'
                        replicon = repliconName
                        consensus =  outTempPrefix + isolate + '_cns.fq'
                        repliconStats = outMerge + refName + '_' + repliconName + '_RepStats.txt'
                        yield([input, output, replicon, consensus,repliconStats, flagFile])

            @follows(getConsensus, getMergeConsensus)
            @follows(getRepSNPList)
            @files(matrixEntryByCoreRep)
            def deriveRepAlleleMatrix(input, output, replicon, consensus, repliconStats, flagFile):
                runStageCheck('deriveRepAlleleMatrix', flagFile, input, output, reference, replicon, consensus, repliconStats)

            def matrixByCoreRep():
                for repliconName in core_replicons:
                    input = outTempPrefix + refName + '_' + repliconName + '_'+full_sequence_list[0]+'_alleles.txt'
                    length_to_remove = len(full_sequence_list[0])+8
                    output  = outMerge + refName + '_' + repliconName + '_alleles.csv'
                    flagFile = outSuccessPrefix + refName + '_' + repliconName + '.collateRepAlleleMatrix.Success'
                    yield([input, output, length_to_remove, flagFile])

            @follows(deriveRepAlleleMatrix)
            @files(matrixByCoreRep)
            def collateRepAlleleMatrix(input, output, length_to_remove, flagFile):
                runStageCheck('collateRepAlleleMatrix', flagFile, input, output, length_to_remove)

        else: #runType == 'phylogeny'
            # generate the allele matrix entry for each isolate for each replicon
            def matrixEntryByRep():
                for isolate in full_sequence_list:
                    for repliconName in replicons:
                        input = outTempPrefix + refName + '_' + repliconName[0] + '_SNPList.txt'
                        output  = outTempPrefix + refName + '_' + repliconName[0] + '_' + isolate + '_alleles.txt'
                        flagFile = outSuccessPrefix + refName + '_' + repliconName[0] + '_' + isolate + '.deriveRepAlleleMatrix.Success'
                        replicon = repliconName[0]
                        consensus =  outTempPrefix + isolate + '_cns.fq'
                        repliconStats = outMerge + refName + '_' + repliconName[0] + '_RepStats.txt'
                        yield([input, output, replicon, consensus,repliconStats, flagFile])

            @follows(getConsensus, getMergeConsensus)
            @follows(getRepSNPList)
            @files(matrixEntryByRep)
            def deriveRepAlleleMatrix(input, output, replicon, consensus, repliconStats, flagFile):
                runStageCheck('deriveRepAlleleMatrix', flagFile, input, output, reference, replicon, consensus, repliconStats)

            def matrixByRep():
                for repliconName in replicons:
                    input = outTempPrefix + refName + '_' + repliconName[0] + '_'+full_sequence_list[0]+'_alleles.txt'
                    length_to_remove = len(full_sequence_list[0])+8
                    output  = outMerge + refName + '_' + repliconName[0] + '_alleles.csv'
                    flagFile = outSuccessPrefix + refName + '_' + repliconName[0] + '.collateRepAlleleMatrix.Success'
                    yield([input, output, length_to_remove, flagFile])

            @follows(deriveRepAlleleMatrix)
            @files(matrixByRep)
            def collateRepAlleleMatrix(input, output, length_to_remove, flagFile):
                runStageCheck('collateRepAlleleMatrix', flagFile, input, output, length_to_remove)

        # create distance matrices based on pair-wise differences in SNPs
        @transform(collateRepAlleleMatrix, regex(r"(.*)\/(.+)_alleles.csv"), [outMerge + r"\2_SNP_diff.nxs", outSuccessPrefix + r"\2_alleles.getDifferenceMatrix.Success"])        
        def getDifferenceMatrix(input, outputs):
            output, flagFile = outputs
            runStageCheck('getDifferenceMatrix', flagFile, input)        

        # parse SNP table to create alignment for tree and SNP consequences (tab-delimited file)
        # @transform(collateRepAlleleMatrix, regex(r"(.*)\/(.+)_alleles.csv"), [outMerge + r"\2_alleles.mfasta", outSuccessPrefix + r"\2_alleles.parseSNPs.Success"])
        # def parseSNPs(inputs, outputs):
        #     output, flagFile = outputs
        #     input, _success = inputs
        #     runStageCheck('parseSNPs', flagFile, outMerge, genbank, input)

        # parse SNP table to create alignment for tree
        @transform(collateRepAlleleMatrix, regex(r"(.*)\/(.+)_alleles.csv"), [outMerge + r"\2_alleles.mfasta", outSuccessPrefix + r"\2_alleles.parseSNPsNoGBK.Success"])
        def parseSNPsNoGBK(input, outputs):
            output, flagFile = outputs
            runStageCheck('parseSNPsNoGBK', flagFile, outPrefix, input)
    
        # generate tree - eventually more than one option
        @transform(parseSNPsNoGBK, regex(r"(.*)\/(.+)_alleles.mfasta"), [outMerge + r"\2_alleles.tree", outSuccessPrefix + r"\2_alleles.makeTree.Success"])
        def makeTree(inputs, outputs):
            output, flagFile = outputs
            input, _success = inputs
            runStageCheck('makeTree', flagFile, input, output)

    else: #ie. mergeReads == "" and refGenbank == True
        # generate the gene cover and depth matrices
        @follows(getRepSNPList)
        @transform(getCoverage, regex(r"(.*)\/(.+)_coverage.txt"), [outTempPrefix + r'\2_CoverDepthMatrix.txt', outSuccessPrefix + r'\2.deriveAllRepGeneCover.Success'])
        def deriveAllRepGeneCover(inputs, outputs):
            output, flagFile = outputs
            input, _success = inputs
            runStageCheck('deriveAllRepGeneCover', flagFile, outTempPrefix, genbank, input)

        @merge(deriveAllRepGeneCover, [outPrefix + refName + "_CoverMatrix.csv", outSuccessPrefix + refName + "_CoverMatrix.collateAllRepGeneCover.Success"])
        def collateAllRepGeneCover(inputs, outputs):
            output, flagFile = outputs
            runStageCheck('collateAllRepGeneCover', flagFile, outTempPrefix, outPrefix, refName)

        # parse gene cover (and depth - to come) matrices to summarise gene content
        @transform(collateAllRepGeneCover, regex(r"(.*)\/(.+)_CoverMatrix.csv"), [outPrefix + r"\2_GeneSummary.csv", outSuccessPrefix + r"\2_alleles.parseGeneContent.Success"])
        def parseGeneContent(inputs, outputs):
            output, flagFile = outputs
            (prefix, name, ext) = splitPath(output)
            output2 = prefix + "/" + name[:-11] + "PresenceAbsence.csv"
            input, _success = inputs
            runStageCheck('parseGeneContent', flagFile, input, output, output2)

        if runType == 'pangenome':
            # generate the allele matrix entry for each isolate for each replicon
            def matrixEntryByCoreRep():
                for isolate in full_sequence_list:
                    for repliconName in core_replicons:
                        input = outTempPrefix + refName + '_' + repliconName + '_SNPList.txt'
                        output  = outTempPrefix + refName + '_' + repliconName + '_' + isolate + '_alleles.txt'
                        flagFile = outSuccessPrefix + refName + '_' + repliconName + '_' + isolate + '.deriveRepAlleleMatrix.Success'
                        replicon = repliconName
                        consensus =  outTempPrefix + isolate + '_cns.fq'
                        repliconStats = outPrefix + refName + '_' + repliconName + '_RepStats.txt'
                        yield([input, output, replicon, consensus,repliconStats, flagFile])

            @follows(getConsensus)
            @follows(getRepSNPList)
            @files(matrixEntryByCoreRep)
            def deriveRepAlleleMatrix(input, output, replicon, consensus, repliconStats, flagFile):
                runStageCheck('deriveRepAlleleMatrix', flagFile, input, output, reference, replicon, consensus, repliconStats)

            def matrixByCoreRep():
                for repliconName in core_replicons:
                    input = outTempPrefix + refName + '_' + repliconName + '_'+full_sequence_list[0]+'_alleles.txt'
                    length_to_remove = len(full_sequence_list[0])+8
                    output  = outPrefix + refName + '_' + repliconName + '_alleles.csv'
                    flagFile = outSuccessPrefix + refName + '_' + repliconName + '.collateRepAlleleMatrix.Success'
                    yield([input, output, length_to_remove, flagFile])

            @follows(deriveRepAlleleMatrix)
            @files(matrixByCoreRep)
            def collateRepAlleleMatrix(input, output, length_to_remove, flagFile):
                runStageCheck('collateRepAlleleMatrix', flagFile, input, output, length_to_remove)

        else: #runType == 'phylogeny'
            # generate the allele matrix entry for each isolate for each replicon
            def matrixEntryByRep():
                for isolate in full_sequence_list:
                    for repliconName in replicons:
                        input = outTempPrefix + refName + '_' + repliconName[0] + '_SNPList.txt'
                        output  = outTempPrefix + refName + '_' + repliconName[0] + '_' + isolate + '_alleles.txt'
                        flagFile = outSuccessPrefix + refName + '_' + repliconName[0] + '_' + isolate + '.deriveRepAlleleMatrix.Success'
                        replicon = repliconName[0]
                        consensus =  outTempPrefix + isolate + '_cns.fq'
                        repliconStats = outPrefix + refName + '_' + repliconName[0] + '_RepStats.txt'
                        yield([input, output, replicon, consensus,repliconStats, flagFile])

            @follows(getConsensus)
            @follows(getRepSNPList)
            @files(matrixEntryByRep)
            def deriveRepAlleleMatrix(input, output, replicon, consensus, repliconStats, flagFile):
                runStageCheck('deriveRepAlleleMatrix', flagFile, input, output, reference, replicon, consensus, repliconStats)

            def matrixByRep():
                for repliconName in replicons:
                    input = outTempPrefix + refName + '_' + repliconName[0] + '_'+full_sequence_list[0]+'_alleles.txt'
                    length_to_remove = len(full_sequence_list[0])+8
                    output  = outPrefix + refName + '_' + repliconName[0] + '_alleles.csv'
                    flagFile = outSuccessPrefix + refName + '_' + repliconName[0] + '.collateRepAlleleMatrix.Success'
                    yield([input, output, length_to_remove, flagFile])

            @follows(deriveRepAlleleMatrix)
            @files(matrixByRep)
            def collateRepAlleleMatrix(input, output, length_to_remove, flagFile):
                runStageCheck('collateRepAlleleMatrix', flagFile, input, output, length_to_remove)

        # create distance matrices based on pair-wise differences in SNPs
        @transform(collateRepAlleleMatrix, regex(r"(.*)\/(.+)_alleles.csv"), [outPrefix + r"\2_SNP_diff.nxs", outSuccessPrefix + r"\2_alleles.getDifferenceMatrix.Success"])        
        def getDifferenceMatrix(input, outputs):
            output, flagFile = outputs
            runStageCheck('getDifferenceMatrix', flagFile, input)        

        # parse SNP table to create alignment for tree
        @transform(collateRepAlleleMatrix, regex(r"(.*)\/(.+)_alleles.csv"), [outPrefix + r"\2_alleles.mfasta", outSuccessPrefix + r"\2_alleles.parseSNPsNoGBK.Success"])
        def parseSNPsNoGBK(input, outputs):
            output, flagFile = outputs
            runStageCheck('parseSNPsNoGBK', flagFile, outPrefix, input)

        # generate tree - eventually more than one option
        @transform(parseSNPsNoGBK, regex(r"(.*)\/(.+)_alleles.mfasta"), [outPrefix + r"\2_alleles.tree", outSuccessPrefix + r"\2_alleles.makeTree.Success"])
        def makeTree(inputs, outputs):
            output, flagFile = outputs
            input, _success = inputs
            runStageCheck('makeTree', flagFile, input, output)
  
else: # refGenbank == False
    if outMerge != "":
        # get consensus sequence for merged set
        bamPatterns = outMergeBam + '*.bam'
        bams = []
        if type(bamPatterns) == list:
            for pattern in bamPatterns:
                bams.append(glob.glob(pattern))
        else:
            bams = glob.glob(bamPatterns)        
        @follows(getRepSNPList)
        @transform(bams, regex(r"(.*)\/(.+).bam"), [outTempPrefix + r"\2_cns.fq", outSuccessPrefix + r"\2.getMergeConsensus.Success"])
        def getMergeConsensus(input, outputs):
            output, flagFile = outputs
            runStageCheck('getConsensus', flagFile, reference, input, output)

        if runType == 'pangenome':
            # generate the allele matrix entry for each isolate for each replicon
            def matrixEntryByCoreRep():
                for isolate in full_sequence_list:
                    for repliconName in core_replicons:
                        input = outTempPrefix + refName + '_' + repliconName + '_SNPList.txt'
                        output  = outTempPrefix + refName + '_' + repliconName + '_' + isolate + '_alleles.txt'
                        flagFile = outSuccessPrefix + refName + '_' + repliconName + '_' + isolate + '.deriveRepAlleleMatrix.Success'
                        replicon = repliconName
                        consensus =  outTempPrefix + isolate + '_cns.fq'
                        repliconStats = outMerge + refName + '_' + repliconName + '_RepStats.txt'
                        yield([input, output, replicon, consensus,repliconStats, flagFile])

            @follows(getConsensus, getMergeConsensus)
            @follows(getRepSNPList)
            @files(matrixEntryByCoreRep)
            def deriveRepAlleleMatrix(input, output, replicon, consensus, repliconStats, flagFile):
                runStageCheck('deriveRepAlleleMatrix', flagFile, input, output, reference, replicon, consensus, repliconStats)

            def matrixByCoreRep():
                for repliconName in core_replicons:
                    input = outTempPrefix + refName + '_' + repliconName + '_'+full_sequence_list[0]+'_alleles.txt'
                    length_to_remove = len(full_sequence_list[0])+8
                    output  = outMerge + refName + '_' + repliconName + '_alleles.csv'
                    flagFile = outSuccessPrefix + refName + '_' + repliconName + '.collateRepAlleleMatrix.Success'
                    yield([input, output, length_to_remove, flagFile])

            @follows(deriveRepAlleleMatrix)
            @files(matrixByCoreRep)
            def collateRepAlleleMatrix(input, output, length_to_remove, flagFile):
                runStageCheck('collateRepAlleleMatrix', flagFile, input, output, length_to_remove)

        else: #runType == 'phylogeny'
            # generate the allele matrix entry for each isolate for each replicon
            def matrixEntryByRep():
                for isolate in full_sequence_list:
                    for repliconName in replicons:
                        input = outTempPrefix + refName + '_' + repliconName[0] + '_SNPList.txt'
                        output  = outTempPrefix + refName + '_' + repliconName[0] + '_' + isolate + '_alleles.txt'
                        flagFile = outSuccessPrefix + refName + '_' + repliconName[0] + '_' + isolate + '.deriveRepAlleleMatrix.Success'
                        replicon = repliconName[0]
                        consensus =  outTempPrefix + isolate + '_cns.fq'
                        repliconStats = outMerge + refName + '_' + repliconName[0] + '_RepStats.txt'
                        yield([input, output, replicon, consensus,repliconStats, flagFile])

            @follows(getConsensus, getMergeConsensus)
            @follows(getRepSNPList)
            @files(matrixEntryByRep)
            def deriveRepAlleleMatrix(input, output, replicon, consensus, repliconStats, flagFile):
                runStageCheck('deriveRepAlleleMatrix', flagFile, input, output, reference, replicon, consensus, repliconStats)

            def matrixByRep():
                for repliconName in replicons:
                    input = outTempPrefix + refName + '_' + repliconName[0] + '_'+full_sequence_list[0]+'_alleles.txt'
                    length_to_remove = len(full_sequence_list[0])+8
                    output  = outMerge + refName + '_' + repliconName[0] + '_alleles.csv'
                    flagFile = outSuccessPrefix + refName + '_' + repliconName[0] + '.collateRepAlleleMatrix.Success'
                    yield([input, output, length_to_remove, flagFile])

            @follows(deriveRepAlleleMatrix)
            @files(matrixByRep)
            def collateRepAlleleMatrix(input, output, length_to_remove, flagFile):
                runStageCheck('collateRepAlleleMatrix', flagFile, input, output, length_to_remove)

        # create distance matrices based on pair-wise differences in SNPs
        @transform(collateRepAlleleMatrix, regex(r"(.*)\/(.+)_alleles.csv"), [outMerge + r"\2_SNP_diff.nxs", outSuccessPrefix + r"\2_alleles.getDifferenceMatrix.Success"])        
        def getDifferenceMatrix(input, outputs):
            output, flagFile = outputs
            runStageCheck('getDifferenceMatrix', flagFile, input)         

        # parse SNP table to create alignment for tree
        @transform(collateRepAlleleMatrix, regex(r"(.*)\/(.+)_alleles.csv"), [outMerge + r"\2_alleles.mfasta", outSuccessPrefix + r"\2_alleles.parseSNPsNoGBK.Success"])
        def parseSNPsNoGBK(input, outputs):
            output, flagFile = outputs
            runStageCheck('parseSNPsNoGBK', flagFile, outMerge, input)

        # generate tree - eventually more than one option
        @transform(parseSNPsNoGBK, regex(r"(.*)\/(.+)_alleles.mfasta"), [outMerge + r"\2_alleles.tree", outSuccessPrefix + r"\2_alleles.makeTree.Success"])
        def makeTree(inputs, outputs):
            output, flagFile = outputs
            input, _success = inputs
            runStageCheck('makeTree', flagFile, input, output)

    else: #refGenbank == False and outMerge == ''

        if runType == 'pangenome':
            # generate the allele matrix entry for each isolate for each replicon
            def matrixEntryByCoreRep():
                for isolate in full_sequence_list:
                    for repliconName in core_replicons:
                        input = outTempPrefix + refName + '_' + repliconName + '_SNPList.txt'
                        output  = outTempPrefix + refName + '_' + repliconName + '_' + isolate + '_alleles.txt'
                        flagFile = outSuccessPrefix + refName + '_' + repliconName + '_' + isolate + '.deriveRepAlleleMatrix.Success'
                        replicon = repliconName
                        consensus =  outTempPrefix + isolate + '_cns.fq'
                        repliconStats = outPrefix + refName + '_' + repliconName + '_RepStats.txt'
                        yield([input, output, replicon, consensus,repliconStats, flagFile])

            @follows(getConsensus)
            @follows(getRepSNPList)
            @files(matrixEntryByCoreRep)
            def deriveRepAlleleMatrix(input, output, replicon, consensus, repliconStats, flagFile):
                runStageCheck('deriveRepAlleleMatrix', flagFile, input, output, reference, replicon, consensus, repliconStats)

            def matrixByCoreRep():
                for repliconName in core_replicons:
                    input = outTempPrefix + refName + '_' + repliconName + '_'+full_sequence_list[0]+'_alleles.txt'
                    length_to_remove = len(full_sequence_list[0])+8
                    output  = outPrefix + refName + '_' + repliconName + '_alleles.csv'
                    flagFile = outSuccessPrefix + refName + '_' + repliconName + '.collateRepAlleleMatrix.Success'
                    yield([input, output, length_to_remove, flagFile])

            @follows(deriveRepAlleleMatrix)
            @files(matrixByCoreRep)
            def collateRepAlleleMatrix(input, output, length_to_remove, flagFile):
                runStageCheck('collateRepAlleleMatrix', flagFile, input, output, length_to_remove)

        else: #runType == 'phylogeny'
            # generate the allele matrix entry for each isolate for each replicon
            def matrixEntryByRep():
                for isolate in full_sequence_list:
                    for repliconName in replicons:
                        input = outTempPrefix + refName + '_' + repliconName[0] + '_SNPList.txt'
                        output  = outTempPrefix + refName + '_' + repliconName[0] + '_' + isolate + '_alleles.txt'
                        flagFile = outSuccessPrefix + refName + '_' + repliconName[0] + '_' + isolate + '.deriveRepAlleleMatrix.Success'
                        replicon = repliconName[0]
                        consensus =  outTempPrefix + isolate + '_cns.fq'
                        repliconStats = outPrefix + refName + '_' + repliconName[0] + '_RepStats.txt'
                        yield([input, output, replicon, consensus,repliconStats, flagFile])

            @follows(getConsensus)
            @follows(getRepSNPList)
            @files(matrixEntryByRep)
            def deriveRepAlleleMatrix(input, output, replicon, consensus, repliconStats, flagFile):
                runStageCheck('deriveRepAlleleMatrix', flagFile, input, output, reference, replicon, consensus, repliconStats)

            def matrixByRep():
                for repliconName in replicons:
                    input = outTempPrefix + refName + '_' + repliconName[0] + '_'+full_sequence_list[0]+'_alleles.txt'
                    length_to_remove = len(full_sequence_list[0])+8
                    output  = outPrefix + refName + '_' + repliconName[0] + '_alleles.csv'
                    flagFile = outSuccessPrefix + refName + '_' + repliconName[0] + '.collateRepAlleleMatrix.Success'
                    yield([input, output, length_to_remove, flagFile])

            @follows(deriveRepAlleleMatrix)
            @files(matrixByRep)
            def collateRepAlleleMatrix(input, output, length_to_remove, flagFile):
                runStageCheck('collateRepAlleleMatrix', flagFile, input, output, length_to_remove)

        # create distance matrices based on pair-wise differences in SNPs
        @transform(collateRepAlleleMatrix, regex(r"(.*)\/(.+)_alleles.csv"), [outPrefix + r"\2_SNP_diff.nxs", outSuccessPrefix + r"\2_alleles.getDifferenceMatrix.Success"])        
        def getDifferenceMatrix(input, outputs):
            output, flagFile = outputs
            runStageCheck('getDifferenceMatrix', flagFile, input)        

        # parse SNP table to create alignment for tree
        @transform(collateRepAlleleMatrix, regex(r"(.*)\/(.+)_alleles.csv"), [outPrefix + r"\2_alleles.mfasta", outSuccessPrefix + r"\2_alleles.parseSNPsNoGBK.Success"])
        def parseSNPsNoGBK(input, outputs):
            output, flagFile = outputs
            runStageCheck('parseSNPsNoGBK', flagFile, outPrefix, input)

        # generate tree - eventually more than one option
        @transform(parseSNPsNoGBK, regex(r"(.*)\/(.+)_alleles.mfasta"), [outPrefix + r"\2_alleles.tree", outSuccessPrefix + r"\2_alleles.makeTree.Success"])
        def makeTree(inputs, outputs):
            output, flagFile = outputs
            input, _success = inputs
            runStageCheck('makeTree', flagFile, input, output)

# *** Clean up *** 
if outMerge != "":
    if refGenbank == False:
        # delete output directory to finish
        @follows(getDifferenceMatrix, makeTree)
        @files(input==None, outMerge + "finish.deleteDir.Success")
        def deleteDir(input, flagFile):
            sequence_list_file = open((outMerge + 'sequence_list.txt') , "w")
            for item in full_sequence_list:
                sequence_list_file.write(item +'\n')
            sequence_list_file.close()
            runStageCheck('deleteDir', flagFile, outPrefix)

    else:
        # delete output directory to finish
        @follows(parseGeneContent, getDifferenceMatrix, makeTree)
        @files(input==None, outMerge + "finish.deleteDir.Success")
        def deleteDir(input, flagFile):
            sequence_list_file = open((outMerge + 'sequence_list.txt') , "w")
            for item in full_sequence_list:
                sequence_list_file.write(item +'\n')
            sequence_list_file.close()
            runStageCheck('deleteDir', flagFile, outPrefix)    

else:
    if refGenbank == False:
        # delete outTemp directory to finish
        @follows(getDifferenceMatrix, makeTree)
        @files(input==None, outPrefix + "finish.deleteDir.Success")
        def deleteDir(input, flagFile):
            sequence_list_file = open((outPrefix + 'sequence_list.txt') , "w")
            for item in full_sequence_list:
                sequence_list_file.write(item +'\n')
            sequence_list_file.close()
            runStageCheck('deleteDir', flagFile, outTempPrefix)
    else:
        # delete outTemp directory to finish
        @follows(parseGeneContent, getDifferenceMatrix, makeTree)
        @files(input==None, outPrefix + "finish.deleteDir.Success")
        def deleteDir(input, flagFile):
            sequence_list_file = open((outPrefix + 'sequence_list.txt') , "w")
            for item in full_sequence_list:
                sequence_list_file.write(item +'\n')
            sequence_list_file.close()
            runStageCheck('deleteDir', flagFile, outTempPrefix)

#end of pipeline