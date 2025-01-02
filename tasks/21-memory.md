We want to implement a memory strategy, to compact the memory of the AI.

quantalogic/memory.py

The idea is to create method to memory called compact.

The idea is to keeps the system message + the first two pairs of message user and assistant, and the last two pairs of message user and assistant.

Update quantalogic/memory.py
