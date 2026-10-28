from dataclasses import dataclass
import math
@dataclass
class Bar:
    time:int;open:float;high:float;low:float;close:float;ticks:int
START = 1767225600


def sr_bars(direction=1, start=START):
    bars = []
    for i in range(63):
        close = 1.1005+.0003*math.sin(i*math.pi/4)
        bars.append(Bar(start-(64-i)*300,close-.00001,close+.00025,close-.00025,close,10))
    bars.append(Bar(start-300,1.10000,1.10020,1.09980,1.10015,30))
    if direction < 0:
        bars = [Bar(b.time,2.2-b.open,2.2-b.low,2.2-b.high,2.2-b.close,b.ticks) for b in bars]
    return bars

