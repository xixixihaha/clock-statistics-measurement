from math import sqrt

from saleae.range_measurements import DigitalMeasurer

EDGES_RISING = 'edgesRising'
EDGES_FALLING = 'edgesFalling'
# NOTE: currently f_avg = 1/T_avg, which is strictly speaking not the arithmetic mean of the frequency
FREQUENCY_AVG = 'frequencyAvg'
FREQUENCY_MIN = 'frequencyMin'
FREQUENCY_MAX = 'frequencyMax'
PERIOD_STD_DEV = 'periodStdDev'
POSITIVE_MAX = 'positiveMax'
POSITIVE_MIN = 'positiveMin'
NEGATIVE_MAX = 'negativeMax'
NEGATIVE_MIN = 'negativeMin'
POSITIVE_WIDTH = 'positiveWidth'
NEGATIVE_WIDTH = 'negativeWidth'

class ClockStatsMeasurer(DigitalMeasurer):
    supported_measurements = [EDGES_RISING, EDGES_FALLING, FREQUENCY_AVG, PERIOD_STD_DEV, FREQUENCY_MIN, FREQUENCY_MAX, POSITIVE_MAX, POSITIVE_MIN, NEGATIVE_MAX, NEGATIVE_MIN,POSITIVE_WIDTH,NEGATIVE_WIDTH]

    def __init__(self, requested_measurements):
        super().__init__(requested_measurements)
        # We always need rising/falling edges
        self.edges_rising = 0
        self.edges_falling = 0
        self.first_transition_type = None
        self.first_transition_time = None
        self.last_transition_of_first_type_time = None

        self.period_min = None
        self.period_max = None
        self.full_period_count = 0
        self.running_mean_period = 0
        self.running_m2_period = 0
        
        self.prevTime = None
        self.pos_max = None
        self.pos_min = None
        self.neg_max = None
        self.neg_min = None
        self.pos_width = None
        self.neg_width = None

    def process_data(self, data):
        for t, bitstate in data:
            if self.first_transition_type is None:
                self.first_transition_type = bitstate
                self.first_transition_time = t
            elif self.first_transition_type == bitstate:
                current_period = t - (self.last_transition_of_first_type_time if self.last_transition_of_first_type_time is not None else self.first_transition_time)
                self.last_transition_of_first_type_time = t

                if self.period_min is None or self.period_min > current_period:
                    self.period_min = current_period
                elif self.period_max is None or self.period_max < current_period:
                    self.period_max = current_period

                # This uses Welford's online algorithm for calculating a variance
                self.full_period_count += 1
                delta = float(current_period) - self.running_mean_period
                self.running_mean_period += delta / self.full_period_count
                delta2 = float(current_period) - self.running_mean_period
                self.running_m2_period += delta * delta2

            if self.prevTime is None:
                self.prevTime = t
            else:
                diff = t - self.prevTime
                if bitstate:
                    if self.neg_max is None or  self.neg_max < diff:
                        self.neg_max = diff
                    if self.neg_min is None or self.neg_min > diff:
                        self.neg_min = diff
                    self.neg_width += diff
                else:
                    if self.pos_max is None or self.pos_max < diff:
                        self.pos_max = diff
                    if self.pos_min is None or self.pos_min > diff:
                        self.pos_min = diff
                    self.pos_width += diff
                self.prevTime = t
                
            if bitstate:
                self.edges_rising += 1
            else:
                self.edges_falling += 1
    
    def measure(self):
        values = {}

        if EDGES_RISING in self.requested_measurements:
            values[EDGES_RISING] = self.edges_rising

        if EDGES_FALLING in self.requested_measurements:
            values[EDGES_FALLING] = self.edges_falling

        if FREQUENCY_AVG in self.requested_measurements:
            if self.first_transition_time is not None and self.last_transition_of_first_type_time is not None:
                # To make the frequency measurement insensitive to exactly where the measurement falls relative to the edge, we only use the
                # sample count of full periods in the range, not the count of samples on the edge.
                #
                # The period count will be the number of transition of the same type as the first transition minus one (fence post problem)
                period_count = (self.edges_rising if self.first_transition_type else self.edges_falling) - 1
                values[FREQUENCY_AVG] = float(period_count) / float(self.last_transition_of_first_type_time - self.first_transition_time)

        if FREQUENCY_MIN in self.requested_measurements:
            if self.period_max is not None and self.period_max != 0:
                values[FREQUENCY_MIN] = 1 / float(self.period_max)

        if FREQUENCY_MAX in self.requested_measurements:
            if self.period_min is not None and self.period_min != 0:
                values[FREQUENCY_MAX] = 1 / float(self.period_min)

        if PERIOD_STD_DEV in self.requested_measurements:
            if self.full_period_count > 1:
                period_variance = self.running_m2_period / (self.full_period_count - 1)
                values[PERIOD_STD_DEV] = sqrt(period_variance)

        if POSITIVE_MAX in self.requested_measurements:
            values[POSITIVE_MAX] = self.pos_max
        if POSITIVE_MIN in self.requested_measurements:
            values[POSITIVE_MIN] = self.pos_min
        if POSITIVE_MIN in self.requested_measurements:
            values[NEGATIVE_MAX] = self.neg_max
        if POSITIVE_MIN in self.requested_measurements:
            values[NEGATIVE_MIN] = self.neg_min

        if POSITIVE_WIDTH in self.requested_measurements:
            values[POSITIVE_WIDTH] = self.pos_width
        if NEGATIVE_WIDTH in self.requested_measurements:
            values[NEGATIVE_WIDTH] = self.neg_width
            
        return values
