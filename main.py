import board
from rpi_ws281x import ws, Color, PixelStrip
from time import sleep
from typing import Iterator, Any, Tuple, List
from itertools import islice
import gzip

from dna import get_consensus_sequence, Locus, Base, RefStatus, read_fai, INVERSE_BASES
from config import (VCF_PATH_PATTERN, CONTIGS, FASTA_PATH, FAI_PATH,
                    N_LEDS, LED_PIN_1, LED_PIN_2, HOMREF_BRIGHTNESS_FACTOR)

BASE_COLORS = {
    Base.T: (255, 0, 0),
    Base.C: (0, 0, 255),
    Base.A: (5, 152, 5),
    Base.G: (209, 103, 6)
}


def init_leds() -> Tuple[PixelStrip, PixelStrip]:
    pixels_strand1 = PixelStrip(N_LEDS, LED_PIN_1)
    pixels_strand2 = PixelStrip(N_LEDS, LED_PIN_2, channel=1)

    pixels_strand1.begin()
    pixels_strand2.begin()
    return (pixels_strand1, pixels_strand2)


def iterate_dna() -> Iterator[str]:
    contig = CONTIGS[2]
    vcf_path = VCF_PATH_PATTERN.format(contig)
    fai_index = read_fai(FAI_PATH, CONTIGS)

    with gzip.open(vcf_path, mode="rt", encoding="utf-8") as vcf_file, \
         open(FASTA_PATH, mode="r", encoding="utf-8") as ref_file:
        for l in get_consensus_sequence(vcf_file, ref_file, fai_index[contig]):
            yield l


def locus_to_colors(l: Locus) -> Tuple[Color, Color]:
    b = l.bases[1]
    c1 = BASE_COLORS[b]
    c2 = BASE_COLORS[INVERSE_BASES[b]]

    if l.ref_status == RefStatus.hom_ref:
        c1 = tuple(int(x * HOMREF_BRIGHTNESS_FACTOR) for x in c1)
        c2 = tuple(int(x * HOMREF_BRIGHTNESS_FACTOR) for x in c2)
    return (Color(*c1), Color(*c2))


def iterate_colors() -> Iterator[Tuple[Color, Color]]:
    return map(locus_to_colors, iterate_dna())


def iterate_color_sequences() -> Iterator[List[Tuple[Color, Color]]]:
    colors_it = iterate_colors()
    res = list(islice(colors_it, N_LEDS))
    yield res
    for e in colors_it:
        res = res[1:] + [e]
        return res

def run():
    strand1, strand2 = init_leds()

    for strand_colors in iterate_color_sequences():
        for i, (c1, c2) in enumerate(strand_colors):
            strand1.setPixelColor(i, c1)
            strand2.setPixelColor(i, c2)
        strand1.show()
        strand2.show()
        sleep(0.5)

if __name__ == "__main__":
    run()