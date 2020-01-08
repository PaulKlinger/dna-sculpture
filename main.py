import board
from rpi_ws281x import ws, Color, PixelStrip
import busio
import adafruit_ssd1306

from time import sleep
from typing import Iterator, Any, Tuple, List, Dict
from itertools import islice
import gzip
import random
import logging

from dna import get_consensus_sequence, Locus, Base, RefStatus, read_fai, INVERSE_BASES
from config import (VCF_PATHS, CONTIGS, FASTA_PATH, FAI_PATH,
                    N_LEDS, LED_PIN_1, LED_PIN_2, HOMREF_BRIGHTNESS_FACTOR,
                    BASES_PER_SECOND, BASES_PER_SECOND_DIFF, JUMP_PROB)


BASE_COLORS = {
    Base.T: (255, 0, 0),
    Base.C: (0, 0, 255),
    Base.A: (5, 152, 5),
    Base.G: (209, 103, 6)
}

FALLBACK_COLOR = (30, 30, 30)


def init_leds() -> Tuple[PixelStrip, PixelStrip]:
    pixels_strand1 = PixelStrip(N_LEDS, LED_PIN_1)
    pixels_strand2 = PixelStrip(N_LEDS, LED_PIN_2, channel=1)

    pixels_strand1.begin()
    pixels_strand2.begin()
    return (pixels_strand1, pixels_strand2)


def init_screen() -> adafruit_ssd1306.SSD1306_I2C:
    i2c = busio.I2C(board.SCL, board.SDA, frequency=800000)
    display = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c)
    display.rotation = 2
    return display

class DNAIterator(object):
    def __init__(self, ref_path: str, contigs: List[str], vcf_paths: Dict[str, str], fai_path: str):
        self.fai_index = read_fai(fai_path, vcf_paths.keys())
        self.contigs = contigs
        self.ref_path = ref_path
        self.vcf_paths = vcf_paths
    
    def iterate_loci(self, contig: str, start_pos: int, skip_start_invalid: bool=True) -> Iterator[Locus]:
        with gzip.open(self.vcf_paths[contig], mode="rt", encoding="utf-8") as vcf_file, \
         open(self.ref_path, mode="r", encoding="utf-8") as ref_file:
            logging.info("starting iteration from {}:{}".format(contig, start_pos))
            consensus_it = get_consensus_sequence(vcf_file, ref_file, self.fai_index[contig], start_pos)
            if skip_start_invalid:
                logging.info("skipping invalids")
                for l in consensus_it:
                    if l.bases[1] in (Base.A, Base.C, Base.T, Base.G):
                        logging.info("reached valid bases")
                        break
            yield from consensus_it
    
    def iterate_from_random(self, skip_start_invalid: bool=True) -> Iterator[Locus]:
        contig = random.choice(self.contigs)
        start_pos = random.randint(0, self.fai_index[contig].len)

        yield from self.iterate_loci(contig, start_pos, skip_start_invalid)

def locus_to_colors(l: Locus) -> Tuple[Color, Color]:
    b = l.bases[1]
    c1 = BASE_COLORS.get(b, FALLBACK_COLOR)
    c2 = BASE_COLORS.get(INVERSE_BASES.get(b, None), FALLBACK_COLOR)

    if l.ref_status == RefStatus.hom_ref:
        c1 = tuple(int(x * HOMREF_BRIGHTNESS_FACTOR) for x in c1)
        c2 = tuple(int(x * HOMREF_BRIGHTNESS_FACTOR) for x in c2)
    return (Color(*c1), Color(*c2))


def iterate_sliding(source_it: Iterator[Any], n: int) -> Iterator[List[Any]]:
    """
    Iterates through source_it returning a sliding window of n outputs
    """
    res = list(islice(source_it, n))
    yield res
    for e in source_it:
        res = res[1:] + [e]
        yield res


def update_screen(display: adafruit_ssd1306.SSD1306_I2C, loci: List[Locus]) -> None:
    display.fill(0)
    display.text("{}: {}".format(loci[0].contig, loci[0].pos), 0, 0, 1)
    display.text("".join(str(l.bases[1]) for l in loci), 0, 10, 1)
    display.show()


def run():
    strand1, strand2 = init_leds()
    display = init_screen()
    dna_iterator = DNAIterator(FASTA_PATH, CONTIGS, VCF_PATHS, FAI_PATH)

    while True:
        random_iter = dna_iterator.iterate_from_random(skip_start_invalid=True)
        for seq in iterate_sliding(random_iter, N_LEDS):
            update_screen(display, seq)
            for i, l in enumerate(seq):
                c1, c2 = locus_to_colors(l)
                strand1.setPixelColor(i, c1)
                strand2.setPixelColor(i, c2)
            strand1.show()
            strand2.show()
            if all(l.ref_status == RefStatus.hom_ref for l in seq):
                sleep(1 / BASES_PER_SECOND)
            else:
                sleep(1 / BASES_PER_SECOND_DIFF)
            if random.random() < JUMP_PROB:
                break

if __name__ == "__main__":
    logging.basicConfig(level="INFO")
    run()
