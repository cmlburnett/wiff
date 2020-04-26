import functools
import operator

class bitfield:
	"""
	Maintains a bit list internally that can be imported/exported from a byte string and manipulated individually.
	Internal bit list auto-expands as bits are manipulated.
	"""
	def __init__(self):
		self._bits = []

	def __len__(self):
		return len(self._bits)

	def __getitem__(self, k):
		return self._bits[k]

	def __setitem__(self, k,v):
		# Expand list size if needed
		if k>=len(self._bits):
			self._bits += [0]*(k+1-len(self._bits))

		self._bits[k] = v

	def append(self, v):
		self._bits.append(v)

	def pop(self):
		return self._bits.pop()

	def push(self, v):
		self._bits.push(v)

	def insert(self, index, v):
		self._bits.insert(index, v)

	def set(self, *vals):
		"""
		For all the indices provided, set the bit.
		"""
		for v in vals:
			self[v] = 1

	def clear(self, *vals):
		"""
		For all the indices provided, clear the bit.
		"""
		for v in vals:
			self[v] = 0

	def set_indices(self):
		"""
		Returns a list of all indices that are set.
		"""
		return [i for i in range(len(self._bits)) if self._bits[i] != 0]

	def clear_indices(self):
		"""
		Returns a list of all indices that are clear.
		"""
		return [i for i in range(len(self._bits)) if self._bits[i] == 0]

	@classmethod
	def from_bytes(cls, bs):
		z = bitfield()
		z._bits = bitfield.bytestobits(bs)

		return z

	def to_bytes(self):
		# Force to 1 or 0
		for i in range(len(self._bits)):
			self._bits[i] = int(self._bits[i] != 0)

		ret = []
		for i in range(0, len(self._bits), 8):
			ret.append(bitfield.bitstobytes(self._bits[i:i+8]))

		return struct.pack("<" + "B"*len(ret), *ret)


	@staticmethod
	def bitstobytes(bits):
		"""
		Convert a list of bits (index 0 is least-significant) into bytes
		"""
		# Have to reverse the order since the reduction is written to start
		# from most significant
		bits.reverse()
		# returns recursive evaluation like (((...)*2 + b2)*2 +b1)*2 + b0
		z = functools.reduce(lambda x,y: x*2+y, bits, 0)
		bits.reverse()
		return z

	@staticmethod
	def bytestobits(bs):
		# Explode into a list of integer bytes
		b = memoryview(bs)
		# Convert to binary strings
		b = [bin(_)[2:].zfill(8) for _ in b]
		# Explode binary strings into integer 1's and 0's
		b = [[int(_) for _ in list(x)] for x in b]
		[_.reverse() for _ in b]

		ret = []

		# Concatenate list of lists into a single list
		functools.reduce(operator.iconcat, b, ret)

		return ret
