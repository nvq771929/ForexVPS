"""Synthetic histories for mechanics tests only; never market/profit evidence."""
import math
from tests.fixtures import Bar,START,sr_bars


def mirror(bars):
    return [Bar(b.time,2.2-b.open,2.2-b.low,2.2-b.high,2.2-b.close,b.ticks) for b in bars]


def trend_bars(direction=1,start=START):
    bars=[]
    for i in range(63):
        close=1.1+.00004*i+.00012*math.sin(i*math.pi/4)
        if i>=60:close=1.1+.00004*59+.00012*math.sin(59*math.pi/4)-.00008*(i-59)
        bars.append(Bar(start-(64-i)*300,close-.00002,close+.00025,close-.00025,close,10))
    price=bars[-1].close
    bars.append(Bar(start-300,price,price+.0004,price-.00005,price+.00035,30))
    return bars if direction>0 else mirror(bars)


def breakout_bars(direction=1,start=START):
    bars=sr_bars(start=start)
    bars[-1]=Bar(start-300,1.1006,1.1017,1.1005,1.1016,30)
    return bars if direction>0 else mirror(bars)
