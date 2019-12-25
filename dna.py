import gzip
from collections import namedtuple
from enum import Enum
from typing import Dict, List, Tuple, TextIO, BinaryIO, Iterator, NamedTuple

FASTA_PATH = "./data/GCA_000001405.15_GRCh38_no_alt_plus_hs38d1_analysis_set.fna"
FAI_PATH = "./data/GCA_000001405.15_GRCh38_no_alt_plus_hs38d1_analysis_set.fna.fai"

VCF_PATHS = [
    "./data/grch38_calls_filtered_chr1.vcf.gz",
]

CHRS = ["chr1",]

class Base(Enum):
    N = 0
    A = 1
    C = 2
    T = 3
    G = 4
    
base_to_enum = {"N": Base.N, "A": Base.A, "C": Base.C, "T": Base.T, "G": Base.G}
    
class Genotype(Enum):
    g00 = 0
    g01 = 1
    g11 = 2
    gxx = 3
    
class RefStatus(Enum):
    hom_ref = 0
    het_mix = 1
    hom_alt = 2
    het_alt = 3
    
    
class Locus(NamedTuple):
    """
    Genotype at one locus. Assumes diploid.

    bases: bases (same for homozygous, different for heterozygous)
    ref_status: relation to reference
    """
    bases: Tuple[Base, Base]
    ref_status: RefStatus

VcfLine = namedtuple("VcfLine",
    ["chr", "pos", "id", "ref", "alt",
     "qual", "filter", "info", "gt", "pl"])
VcfLine.__doc__ = """
An entry in a Variant Call File

chr: chromosome
pos: position in chromosome
id: unused
ref: reference base(s)
alt: alternative bases
qual: quality score
filter: 'PASS' if valid
info: 
gt: inferred genotype 0/0 homozygous ref, 0/1 heterozygous, 1/1 homozygous alt
pl: phred scaled probability of each genotype in order above (lower is more likely)
"""

FaiLine = namedtuple("FaiLine",
    ["contig", "len", "start", "bapl", "bypl"])
FaiLine.__doc__ = """
An entry in a Fai file

contig: name of contig (i.e. chromosome)
len: # of bases in contig
start: byte index of contig start in fasta file
bapl: # of bases per line
bypl: # of bytes per line
"""

def read_fai(filename: str, contigs: List[str]) -> Dict[str, FaiLine]:
    fai_index = {}

    with open(FAI_PATH, encoding="utf-8") as f:
        for line in f:
            cols = line.strip().split("\t")
            if cols[0] in contigs:
                fai_index[cols[0]] = FaiLine(cols[0],
                                             *[int(x) for x in cols[1:]])
    return fai_index

fai_index = read_fai(FAI_PATH, CHRS)
print(fai_index)

def iterate_vcf(vcf_file: TextIO, contig: str) -> Iterator[VcfLine]:
    for line in vcf_file:
        if not line.startswith(contig):
            continue
        cols = line.strip().split("\t")
        entry = VcfLine(
            cols[0],
            int(cols[1]),
            *cols[2:-2],
            *cols[-1].split(":")
            )
        yield entry
      

def get_consensus_sequence(vcf_file: TextIO, ref_file: TextIO, fai_line: FaiLine) -> Iterator[Locus]:
    vcf_iter = iterate_vcf(vcf_file, fai_line.contig)
    next_variant = next(vcf_iter, None)
    ref_file.seek(fai_line.start)
    
    base_iterator = (base_to_enum[c] for line in ref_file for c in line if c in "ACTGN")
    
    print(fai_line)
    for i, base in enumerate(base_iterator, start=1):
        if i > fai_line.len:
            raise StopIteration()
        if i % 1E6 == 0:
            print(i)
        
        
        if next_variant is not None and i == next_variant.pos:
            variants = []
            while i == next_variant.pos:
                variants.append(next_variant)
                next_variant = next(vcf_iter, None)
                
            for var in variants:
                print(i, base, var.ref, var.alt)
            if len(variants) > 1:
                print("Multiple colocated variants!")
                input()
            continue
        
        yield Locus((base, base), RefStatus.hom_ref)
        
    
            


with gzip.open(VCF_PATHS[0], mode="rt", encoding="utf-8") as vcf_file, \
    open(FASTA_PATH, mode="r", encoding="utf-8") as ref_file:
    
    for l in get_consensus_sequence(vcf_file, ref_file, fai_index["chr1"]):
        pass
    