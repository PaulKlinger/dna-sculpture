import gzip
from collections import namedtuple
from enum import Enum
from typing import Dict, List, Tuple, TextIO, BinaryIO, Iterator, NamedTuple
import logging
from itertools import zip_longest

logger = logging.getLogger()
logger.setLevel("WARN")

class EnumNameOnly(Enum):
    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name


class Base(EnumNameOnly):
    N = 0  # any
    A = 1
    C = 2
    T = 3
    G = 4
    X = 5  # missing
    R = 6  # G/A
    Y = 7  # T/C
    K = 8  # G/T
    M = 9  # A/C
    S = 10  # G/C
    W = 11  # A/T
    B = 12  # G/T/C
    D = 13  # G/A/T
    H = 14  # A/C/T
    V = 15  # G/C/A


B = Base

base_to_enum = {"N": Base.N, "A": Base.A,
                "C": Base.C, "T": Base.T, "G": Base.G,
                "R": Base.R, "Y": Base.Y, "K": Base.K,
                "M": Base.M, "S": Base.S, "W": Base.W,
                "B": Base.B, "D": Base.D, "H": Base.H,
                "V": Base.V}

INVERSE_BASES = {B.A: B.T, B.T: B.A, B.C: B.G, B.G: B.C}

class Genotype(EnumNameOnly):
    g00 = 0
    g01 = 1
    g11 = 2
    gxx = 3


class RefStatus(EnumNameOnly):
    hom_ref = 0
    het_mix = 1
    hom_alt = 2
    het_alt = 3


RS = RefStatus

gt_to_ref_status = {
    (0, 0): RS.hom_ref, (0, 1): RS.het_mix, (1, 1): RS.hom_alt,
    (1, 2): RS.het_alt, (2, 2): RS.hom_alt
}


class Locus(NamedTuple):
    """
    Genotype at one locus. Assumes diploid.

    bases: bases (same for homozygous, different for heterozygous)
    ref_status: relation to reference
    """
    contig: str
    pos: int
    bases: Tuple[Base, Base]
    ref_status: RefStatus


class VariantType(EnumNameOnly):
    SNP = 0
    INS = 1
    DEL = 2
    OTHER = 3  # mostly mix between INS/DEL


VT = VariantType


class Variant(NamedTuple):
    """
    A variant (i.e. one line in a VCF file)

    contig: name of contig in reference
    pos: position in chromosome
    type: SNP/INS/DEL,...
    ref: reference base(s)
    alt: alternative bases
    qual: quality score
    filter: 'PASS' if valid
    info: info column
    gt: inferred genotype 0/0 homozygous ref, 0/1 heterozygous, 1/1 homozygous alt
    pl: phred scaled probability of each genotype in order above (lower is more likely)
    """
    contig: str
    pos: int
    type: VariantType
    ref: List[Base]
    alts: List[List[Base]]
    qual: float
    filter: str
    info: str
    gt: Tuple[int, int]
    pl: str


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


def iterate_vcf(vcf_file: TextIO, contig: str, filter: bool = True) -> Iterator[Variant]:
    for line in vcf_file:
        if not line.startswith(contig):
            continue
        cols = line.strip().split("\t")
        ref = [base_to_enum[c] for c in cols[3]]
        alts = [[base_to_enum[c] for c in cs] for cs in cols[4].split(",")]
        if len(ref) == 1 and all(len(a) == 1 for a in alts):
            v_type = VT.SNP
        elif len(ref) == 1 and all(len(a) > 1 for a in alts):
            v_type = VT.INS
        elif len(ref) > 1 and all(len(a) == 1 for a in alts):
            v_type = VT.DEL
        else:
            v_type = VT.OTHER
        gt, pl = cols[-1].split(":")
        gt = tuple(int(gi) for gi in gt.split("/"))
        v = Variant(contig=cols[0], pos=int(cols[1]), type=v_type,
                    ref=ref, alts=alts, qual=float(cols[5]),
                    filter=cols[6], info=cols[7], gt=gt, pl=pl)
        if filter and v.filter != "PASS":
            continue
        yield v


class InvalidVariantsError(ValueError):
    pass


def filter_variants(variants: List[Variant], contig: str, i: int):
    """
    This tries to filter out incompatible calls, assuming everything should be diploid
    This is sort of useless as we only display one sequence anyway
    so if there are multiple calls at a locus (e.g. an insertion and an SNP)
    we have to choose one in the end.
    """
    variants.sort(key=lambda v: -v.qual)

    if len(variants) > 2:
        logger.warning(
            f"{len(variants)} variant calls at {contig}:{i}, dropping lowest quality non-SNP!")
        new_vs = []
        to_drop = len(variants) - 2
        for v in reversed(variants):
            if to_drop > 0 and v.type != VT.SNP:
                to_drop += 1
                continue
            new_vs.append(v)
        if len(variants) > 2:
            logger.error(
                f"{len(variants)} SNP variant calls at {contig}:{i}???")
        # if there were no non-SNPs drop lowest quality SNPs (should never happen).
        variants = new_vs[:2]

    if len(variants) == 2 and any(v.gt != (0, 1) for v in variants):
        # I think this should only occur if one of the variant calls is an SNP and the other an INDEL
        # although I'm not sure why they wouldn't be combined into one?
        # see https://github.com/samtools/bcftools/issues/552

        if any(v.type == VT.SNP for v in variants):
            # There seem to be some weird INDEL calls, e.g. the one at chr1:4060135
            # is based on only one read but gets a higher quality score then the
            # hom alt call based on 10s of reads
            # TODO: bcftools call seems to make some very clear mistakes when an SNP is
            #       colocated with an insert.
            #       E.g. at chr2:15909961 the SNP is called homozygous alt even though it
            #       appears in exactly 50% of reads! Unfortunately we throw the insert away
            #       here even though it's clearly real.
            #       Probably best to fix this when calling, not in post
            logger.warning(
                f"{contig}:{i} One of 2 variant calls not heterozygous, dropping indel!")
            variants = [v for v in variants if v.type == VT.SNP]
        else:
            logger.warning(
                f"{contig}:{i} One of 2 variant calls not heterozygous, dropping lowest quality!")
            variants = variants[:1]

    return variants


def iterate_ref(ref_file: TextIO, fai_line: FaiLine) -> Iterator[Tuple[int, Base]]:
    contig = fai_line.contig
    ref_file.seek(fai_line.start)
    i = 0
    valid_bases = frozenset(base_to_enum.keys())
    for line in ref_file:
        for c in line.strip():
            if i >= fai_line.len:
                return

            if c in valid_bases:
                i += 1
                yield i, base_to_enum[c]
            elif c == ">":
                logger.warning(
                    f"{contig}:{i} Contig ended prematurely, expected {fai_line.len} bases, got {i}.")
                return
            else:
                logger.error(f"{contig}:{i} Invalid char '{c}' in fasta")


def get_consensus_sequence(vcf_file: TextIO, ref_file: TextIO, fai_line: FaiLine) -> Iterator[Locus]:
    contig = fai_line.contig
    vcf_iter = iterate_vcf(vcf_file, contig)
    next_variant = next(vcf_iter, None)

    reference = iterate_ref(ref_file, fai_line)

    print(fai_line)

    n_diffs = 0
    for i, ref_base in reference:
        if i % 1E6 == 0:
            print(i, n_diffs)

        if next_variant is not None and i == next_variant.pos:
            n_diffs += 1
            variants = [next_variant]
            for next_variant in vcf_iter:
                if i != next_variant.pos:
                    break
                variants.append(next_variant)

            for v in variants:
                if v.ref[0] != ref_base:
                    logger.error(
                        f"{contig}:{i} Difference between VCF ref ({v.ref[0]}) and fasta ref ({ref_base})")

            variants = filter_variants(variants, contig, i)

            # choose the SNP if there is one as the quality scores don't seem comparable
            # between SNP/INDEL
            variant = ([v for v in variants if v.type == VT.SNP] + variants)[0]
            # TODO: use multiple variants where it makes sense
            # e.g. at chr1:50156031 it's pretty clear that it's heterozygous
            # with an insertion on the reference chromosome

            if variant.type == VT.SNP:
                base_options = variant.ref + sum(variant.alts, [])
                bases = tuple(base_options[bi] for bi in variant.gt)
                yield Locus(contig, i, bases, gt_to_ref_status[variant.gt])
            else:
                ref_alts = [variant.ref] + variant.alts
                for b1, b2 in zip_longest(*(ref_alts[vi] for vi in variant.gt), fillvalue=B.X):
                    yield Locus(contig, i, (b1, b2), gt_to_ref_status[variant.gt])

                # we yield from the sequence in the variant, so we need
                # to skip the corresponding bases in the reference
                [next(reference) for _ in variant.ref[1:]]

                # If the next variant starts before this indel ends we have to skip it
                # TODO: This is stupid...
                # the skipped calls might be higher quality than the original one
                while next_variant.pos < i + len(variant.ref):
                    next_variant = next(vcf_iter, None)

            continue

        yield Locus(contig, i, (ref_base, ref_base), RS.hom_ref)


if __name__ == "__main__":
    from config import VCF_PATH_PATTERN, CONTIGS, FASTA_PATH, FAI_PATH

    contig = CONTIGS[2]
    vcf_path = VCF_PATH_PATTERN.format(contig)
    fai_index = read_fai(FAI_PATH, CONTIGS)

    with gzip.open(vcf_path, mode="rt", encoding="utf-8") as vcf_file, \
         open(FASTA_PATH, mode="r", encoding="utf-8") as ref_file:
        for l in get_consensus_sequence(vcf_file, ref_file, fai_index[contig]):
            b = str(l.bases[1])
            if l.ref_status == RS.hom_ref:
                b = b.lower()
            print(b, end="")
