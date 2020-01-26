# RPS-RNN

[![](video_link_image.jpg)](https://youtu.be/C1H_zHTX7Ds "Project video")

I had my DNA sequenced by [dantelabs.com](https://www.dantelabs.com/) (the 30X whole genome sequencing). They provide fastq, aligned bam, and vcf files, but just to understand some more about the process I redid the alignment with [bwa](https://github.com/lh3/bwa) and the variant calling with [bcftools](https://github.com/samtools/bcftools). (There are some issues with the called variants, see comments in dna.py, but that doesn't really matter for this project.) I've released the vcf files as creative commons, they are available [here](https://almoturg.com/paul_klinger_vcf_grch38.zip). Once I figure out a cheap way to share a 34 GiB file I'll put the bam up as well...

The 3D printed parts were printed on my [Prusa MK3S](https://shop.prusa3d.com/en/3d-printers/180-original-prusa-i3-mk3-kit.html) 3d printer. The two parts of the case are held together with three m2 screws that screw into heat-set metal inserts in the top plate. The helices are friction fit into the top part of the case and secured with an m2 screw that screws into the plastic. The base pairs between the two helices are printed in transparent PLA and the holes are filled with short pieces of 4mm PMMA side-glow fiberoptic. I glued a bit of aluminium foil to the end of the fiberoptic (where the two pieces meet in the middle) so the colors of the complementary bases don't mix. The base pairs are just friction fit into the helices, and the LEDs are sort-of retained by the little tabs at the end of the bases, although most of them broke off during assembly.

The electronics are very simple, just a raspberry pi zero w and 18 WS2812B RGB LEDS in two strings of nine.
The LEDS are connected with some 30 AWG wire, soldered directly to them. I assembled the LEDs already inside the two helices, adding one and then pulling the cables through to the next hole. That's absolutely horrible work, I'm pretty amazed it works at all. When putting the connecting transparent parts in they put pressure on the LEDs and it's quite likely that some of the connection fail and you have to fix it in place... 
Theoretically the WS2812B require an external capacitor (except for the new v5 version) but that would make assembly even more horrible. Thankfully it works fine without them.
The second PCB just contains a micro usb connector and a big capacitor, I used the [same PCB as for my satellite tracker](https://github.com/PaulKlinger/satellite_tracker/tree/master/PCBs/auxiliary).

The default I2C baudrate of the raspberry pi zero w is quite low, which limits the display to ~2 fps. Adding
```
dtparam=i2c_arm=on
dtparam=i2c1=on
dtparam=i2c1_baudrate=800000
```
to boot.config fixes this.

The code here is not very nice, and it's pretty slow, mostly because of the display library. But it's just fast enough for ~10 updates per second, which is about the limit of what is nice to look at anyway.
