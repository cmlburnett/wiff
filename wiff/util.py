
import mmap
import os

import bstruct

DATE_FMT = "%Y%m%d %H%M%S.%f"

def twotuplecheck(x):
	"""Coerce a two-tuple of integers into an interval"""
	if isinstance(x, tuple):
		if len(x) == 2 and isinstance(x[0], int) and isinstance(x[1], int):
			return bstruct.interval(*x)
		else:
			raise ValueError("Tuple is not 2 integers")
	elif isinstance(x, bstruct.interval):
		return x
	else:
		raise TypeError("Not a 2-tuple or an interval")

class _filewrap:
	"""
	Internal file wrapper that memory maps (mmap) the file.
	This provides index access to the file.
	"""
	def __init__(self, fname):
		""" Wrap the file with name @fname """
		if not os.path.exists(fname):
			# Have to call open this way as it otherwise means the function defined above
			f = __builtins__['open'](fname, 'wb')
			# Have to write something to memory map it
			f.write(b'\0' *4096)
			f.close()

		self.fname = fname
		# Have to call open this way as it otherwise means the function defined above
		self.f = __builtins__['open'](fname, 'r+b')
		self.mmap = mmap.mmap(self.f.fileno(), 0)
		self.size = os.path.getsize(fname)

	def close(self):
		self.mmap.close()
		self.f.close()

	def resize(self, sz):
		"""Change the size of the memory map and the file"""
		self.mmap.resize(sz)
		self.size = os.path.getsize(self.fname)
	def resize_add(self, delta):
		"""Add bytes to the existing size"""
		self.resize(self.size + delta)

	def __getitem__(self, k):
		"""
		Supply an integer or slice to get binary data
		"""
		return self.mmap[k]

	def __setitem__(self, k,v):
		"""
		Supply an integer or slice and binary data.
		If the data is beyond the file size, NeedResizeException is thrown
		"""
		# Resize map and file upward as needed
		if isinstance(k, slice):
			if k.stop > self.size:
				raise NeedResizeException
		else:
			if k > self.size:
				raise NeedResizeException

		self.mmap[k] = v

class NeedResizeException(Exception):
	"""
	Exception thrown when the underlying file is too small and should be resized.
	"""
	pass

