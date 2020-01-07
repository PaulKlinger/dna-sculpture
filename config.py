FASTA_PATH = "./data/GCA_000001405.15_GRCh38_no_alt_plus_hs38d1_analysis_set.fna"
FAI_PATH = "./data/GCA_000001405.15_GRCh38_no_alt_plus_hs38d1_analysis_set.fna.fai"

VCF_PATH_PATTERN = "./data/grch38_calls_filtered_{contig}.vcf.gz"

CONTIGS = ["chr" + i for i in range(1,23)] + ["chrX", "chrY", "chrM"]

N_LEDS = 9
LED_PIN_1 = 18
LED_PIN_2 = 13
HOMREF_BRIGHTNESS_FACTOR = 0.5