The default I2C of the raspberry pi zero w is quite low, which limits the display to ~2 fps. Adding
```
dtparam=i2c_arm=on
dtparam=i2c1=on
dtparam=i2c1_baudrate=800000
```
to boot.config fixes this.
