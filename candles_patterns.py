def candle_pattern(current, prev, prev_2):
    realbody = abs(current[1] - current[4])
    candle_range = current[2] - current[3]
    # Bullish swing
    if current[3] > prev[3] and prev[3] < prev_2[3]:
        return 'Bullish swing'
    # Bearish swing
    if current[2] < prev[2] and prev[2] > prev_2[2]:
        return 'Bearish swing'
    # Bullish pinbar
    if realbody <= candle_range / 3 and min(current[1], current[4]) > (current[2] + current[3]) / 2 and current[3] < prev[3]:
        return 'Bullish pinbar'
    # Bearish pinbar
    if realbody <= candle_range / 3 and max(current[1], current[4]) < (current[2] + current[3]) / 2 and current[2] > prev[2]:
        return 'Bearish pinbar'

    # Inside bar
    if current[2] < prev[2] and current[3] > prev[3]:
        return 'Inside bar'

    # Outside bar
    if current[2] > prev[2] and current[3] < prev[3]:
        return 'Outside bar'

    # Bullish engulfing
    if current[2] > prev[2] and current[3] < prev[3] and realbody >= 0.8 * candle_range and current[4] > current[1]:
        return 'Bullish engulfing'
    # Bearish engulfing
    if current[2] > prev[2] and current[3] < prev[3] and realbody >= 0.8 * candle_range and current[4] < current[1]:
        return 'Bearish engulfing'

