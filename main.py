import board
from rpi_ws281x import ws, Color, PixelStrip
import busio
import adafruit_ssd1306
import gpiozero

from time import sleep, perf_counter
from typing import Iterator, Any, Tuple, List, Dict
from itertools import islice
import random
import logging
from subprocess import check_call
import queue

from dna import get_consensus_sequence, Locus, Base, RefStatus, read_fai, INVERSE_BASES
from config import (VCF_PATHS, CONTIGS, FASTA_PATH, FAI_PATH,
                    N_LEDS, LED_PIN_1, LED_PIN_2, HOMREF_BRIGHTNESS_FACTOR,
                    BASES_PER_SECOND, BASES_PER_SECOND_DIFF, JUMP_PROB, N_BASES_DISPLAYED)
from minimal_disp_replacements import MinimalMemoryFont


BASE_COLORS = {
    Base.T: (255, 0, 0),
    Base.C: (0, 0, 255),
    Base.A: (5, 152, 5),
    Base.G: (209, 103, 6)
}

FALLBACK_COLOR = (30, 30, 30)


class Screen(object):
    def __init__(self):
        i2c = busio.I2C(board.SCL, board.SDA, frequency=800000)
        self.display: adafruit_ssd1306.SSD1306_I2C = adafruit_ssd1306.SSD1306_I2C(
            128, 64, i2c)
        self.display.rotation = 2

        # replace the font class with a less complicated faster one
        self.display._font = MinimalMemoryFont()

    def update_screen(self, loci: List[Locus]) -> None:
        self.display.fill(0)
        self.display.text("{}: {}".format(
            loci[0].contig, loci[0].pos), 0, 0, 1)
        self.display.text("_" * N_LEDS, 0, 10, 1)
        self.display.text("".join(str(l.bases[1]) for l in loci), 0, 20, 1)
        self.display.text("".join(" " if l.ref_base == l.bases[1]
                                  else str(l.ref_base) for l in loci), 0, 30, 1)
        self._show()

    def show_message(self, message: str) -> None:
        self.display.fill(0)
        self.display.text(message, 10, 15, 1)
        self._show()

    def _show(self) -> None:
        # When the button is pressed this also pulls down the I2C clock line
        # as this is the only pin that can wake the Pi up from halt.
        # This shouldn't matter, as when the button is pressed we shut down anyway.
        try:
            self.display.show()
        except OSError:
            logging.warning("Display comm error. Button pressed?")


class DNAIterator(object):
    def __init__(self, ref_path: str, contigs: List[str], vcf_paths: Dict[str, str], fai_path: str):
        self.fai_index = read_fai(fai_path, vcf_paths.keys())
        self.contigs = contigs
        self.ref_path = ref_path
        self.vcf_paths = vcf_paths

    def iterate_loci(self, contig: str, start_pos: int) -> Iterator[Locus]:
        with open(self.ref_path, mode="r", encoding="utf-8") as ref_file:
            logging.info(
                "starting iteration from {}:{}".format(contig, start_pos))
            consensus_it = get_consensus_sequence(
                self.vcf_paths[contig], ref_file, self.fai_index[contig], start_pos)
            yield from consensus_it

    def iterate_from_random(self, redraw_invalid_start: bool = True) -> Iterator[Locus]:
        contig = random.choice(self.contigs)
        while True:
            start_pos = random.randint(0, self.fai_index[contig].len)
            l_it = self.iterate_loci(contig, start_pos)
            first_base = next(l_it)
            if not first_base.bases[1] in (Base.A, Base.G, Base.T, Base.C):
                continue
            yield first_base
            yield from l_it


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


class DNASculpture(object):
    def __init__(self):
        self.init_leds()
        self.display = Screen()
        self.button = gpiozero.Button(4, bounce_time=0.05)
        self.button.when_released = self.shutdown
        self.running = False

    def init_leds(self) -> None:
        self.strand1 = PixelStrip(N_LEDS, LED_PIN_1)
        self.strand2 = PixelStrip(N_LEDS, LED_PIN_2, channel=1)

        self.strand1.begin()
        self.strand2.begin()

    def shutdown(self) -> None:
        self.running = False
        logging.info("Shutting down")
        sleep(1)
        check_call(['sudo', 'poweroff'])
        sleep(10)

    def run(self) -> None:
        self.display.show_message("Loading DNA data...")
        dna_iterator = DNAIterator(FASTA_PATH, CONTIGS, VCF_PATHS, FAI_PATH)

        self.running = True
        while True:
            random_iter = dna_iterator.iterate_from_random(redraw_invalid_start=True)
            t0 = perf_counter()
            for seq in iterate_sliding(random_iter, N_BASES_DISPLAYED):
                if not self.running:
                    # This can't be in shutdown because the rpi_ws281x library is
                    # not threadsafe (causes segmentation fault).
                    for i in range(N_LEDS):
                        self.strand1.setPixelColor(i, Color(0, 0, 0))
                        self.strand2.setPixelColor(i, Color(0, 0, 0))
                    self.strand1.show()
                    self.strand2.show()
                    
                    while True:
                        # I2C is broken while the button is pressed
                        # hopefully it's released before we shut down...
                        self.display.show_message("")

                self.display.update_screen(seq)
                for i, l in enumerate(seq[:N_LEDS]):
                    c1, c2 = locus_to_colors(l)
                    self.strand1.setPixelColor(i, c1)
                    self.strand2.setPixelColor(i, c2)
                self.strand1.show()
                self.strand2.show()

                t1 = perf_counter()
                tdiff = t1 - t0
                if all(l.ref_status == RefStatus.hom_ref for l in seq[:N_LEDS]):
                    if tdiff > 1 / BASES_PER_SECOND:
                        logging.warning(f"Took {tdiff}s / base!")
                    sleep(max(1 / BASES_PER_SECOND - tdiff, 0))
                else:
                    sleep(max(1 / BASES_PER_SECOND_DIFF - tdiff, 0))
                t0 = perf_counter()
                if random.random() < JUMP_PROB:
                    logging.info("Jumping to new location")
                    self.display.show_message("Jumping to new location...")
                    break


if __name__ == "__main__":
    logging.basicConfig(level="DEBUG")
    dna = DNASculpture()
    dna.run()
