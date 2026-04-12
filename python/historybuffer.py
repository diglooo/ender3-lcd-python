import collections

class HistoryBuffer:
    def __init__(self, max_size):
        self.history = collections.deque(maxlen=max_size)
        self.maxlen=max_size

    def add_sample(self, sample):
        self.history.append(sample)

    def get_history(self):
        return list(self.history)
    
    def get_maxlen(self):
        return self.maxlen