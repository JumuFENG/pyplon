# stock package

from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal

def zdf_from_code(code):
    zdf = 10
    if code.startswith('sz30') or code.startswith('sh68') or code.startswith('30') or code.startswith('68'):
        zdf = 20
    elif code.startswith('bj'):
        zdf = 30
    return zdf

def precious_decimal(precious):
    exp = '0.'
    for i in range(0, precious):
        exp += '0'
    return Decimal(exp)

def zt_priceby(lclose, zdf=10, precious=2):
    ''' 以昨日收盘价计算涨停价格
    '''
    if zdf == 30:
        return float(Decimal(str(lclose * 1.3)).quantize(Decimal('0.00'), ROUND_FLOOR))
    pdec = precious_decimal(precious)
    zprc = float(Decimal(str((int(round(lclose * 100, 0)) + lclose * zdf) / 100.0)).quantize(pdec, ROUND_HALF_UP))
    return zprc

def dt_priceby(lclose, zdf=10, precious=2):
    ''' 以昨日收盘价计算涨停价格
    '''
    if zdf == 30:
        return float(Decimal(str(lclose * 0.7)).quantize(Decimal('0.00'), ROUND_CEILING))
    pdec = precious_decimal(precious)
    dprc = float(Decimal(str((int(round(lclose * 100, 0)) - lclose * zdf) / 100.0)).quantize(pdec, ROUND_HALF_UP))
    return dprc
