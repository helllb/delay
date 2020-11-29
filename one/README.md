# delay-ping
One-way and round-trip delay measurement of ping packets.

## About
This part of the project is for reproducing the results in figures 1 through 4.

## Usage
You can run the experiment with:
```
python3 ping.py [--setup] [--run=RUN --pings=N] [--ntp=T] [--analyse]
```

`--setup`: when toggled, the machines will be set up for the experiment;

`--run=RUN`: when toggled, the machines will run the experiment and the produced files will be downloaded to your computer in the path specified in `ping.ini`. `RUN` can be either `default` (for reproducing the results in figures 1 through 3), or `sizes` (for reproducing the results in figure 4);

`--pings=N`: `N` is the number of ping echo packets sent from the server machine to the client machine;

`--ntp=T`: when toggled, NTP will be enabled in the machines, which will wait `T` seconds for it to converge before sending probe packets.

`--analyse`: when toggled, all data produced by the experiment will be plot.

Make sure to also edit the configuration file with the desired emulated network parameters.
