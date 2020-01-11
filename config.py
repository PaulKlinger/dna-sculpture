FASTA_PATH = "./data/GCA_000001405.15_GRCh38_no_alt_plus_hs38d1_analysis_set.fna"
FAI_PATH = "./data/GCA_000001405.15_GRCh38_no_alt_plus_hs38d1_analysis_set.fna.fai"

VCF_PATH_PATTERN = "./data/grch38_calls_filtered_{contig}.vcf"

CONTIGS = ["chr{}".format(i) for i in range(1,23)] + ["chrX", "chrY", "chrM"]

VCF_PATHS = {c: VCF_PATH_PATTERN.format(contig=c) for c in CONTIGS}

N_LEDS = 9
LED_PIN_1 = 18
LED_PIN_2 = 13
HOMREF_BRIGHTNESS_FACTOR = 0.1


N_BASES_DISPLAYED = 20
JUMP_PROB = 1 / 10000 # probability of jumping to a new location after each base
BASES_PER_SECOND = 6
BASES_PER_SECOND_DIFF = 2