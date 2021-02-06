"""
Utility file.
Nothing here should reference anything else in this library.
"""

import mmap
import os
import struct

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
			# Have to call open this way (I don't want it confused with open() defined at the library level)
			f = __builtins__['open'](fname, 'wb')
			# Have to write something to memory map it
			f.write(b'\0' *4096)
			f.close()

		self.fname = fname
		# Have to call open this way
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
		# If requesting to set space that isn't available, throw an exception for the caller
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

class blob_builder:
	"""
	Wrapper around bytearray() and struct module to append binary data
	from integer data.
	Access Bytes property for the final byte string.
	"""
	def __init__(self):
		self._dat = bytearray()

	def add_u8(self, x): self._dat += struct.pack("<B", x)
	def add_i8(self, x): self._dat += struct.pack("<b", x)

	def add_u16(self, x): self._dat += struct.pack("<H", x)
	def add_i16(self, x): self._dat += struct.pack("<h", x)

	def add_u24(self, x): self._dat += struct.pack("<I", x)[0:3]
	def add_i24(self, x): self._dat += struct.pack("<i", x)[0:3]

	def add_u32(self, x): self._dat += struct.pack("<I", x)
	def add_i32(self, x): self._dat += struct.pack("<i", x)

	def add_u40(self, x): self._dat += struct.pack("<Q", x)[0:5]
	def add_i40(self, x): self._dat += struct.pack("<q", x)[0:5]

	def add_u48(self, x): self._dat += struct.pack("<Q", x)[0:6]
	def add_i48(self, x): self._dat += struct.pack("<q", x)[0:6]

	def add_u56(self, x): self._dat += struct.pack("<Q", x)[0:7]
	def add_i56(self, x): self._dat += struct.pack("<q", x)[0:7]

	def add_u64(self, x): self._dat += struct.pack("<Q", x)
	def add_i64(self, x): self._dat += struct.pack("<q", x)

	@property
	def Bytes(self):
		return bytes(self._dat)

def range2d(x,y):
	"""
	Simple 2-dimensional generator that returns a 2-tuple of x,y values.
	Makes code a little prettier and easier to write.
		for (i,j) in range2d(1000,10):
			...
	"""
	for i in range(x):
		for j in range(y):
			yield (i,j)

def range3d(x,y,z):
	"""
	Simple 3-dimensional generator that returns a 3-tuple of x,y values.
	Makes code a little prettier and easier to write.
		for (i,j,k) in range2d(1000,10,5):
			...
	"""
	for i in range(x):
		for j in range(y):
			for k in range(z):
				yield (i,j,k)

