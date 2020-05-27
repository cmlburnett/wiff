
import struct

import bstruct

from .bits import bitfield
from .wiffchunk import WIFF_chunk
from .structs import wave_struct, channel_struct

class WIFFWAVE:
	"""
	Helper class that interfaces the data portion of a WIFFWAVE chunk.
	This chunk includes the raw binary data in the recording.
	"""

	def __init__(self, wiff, fw, chunk):
		self.wiff = wiff
		self.fw = fw
		self.chunk = chunk
		self._s = wave_struct(fw, chunk.data_offset)

		self._frame_size = None
		self._ser = None
		self._deser = None

	def setup(self):
		"""
		Must be called after creating object on an old chunk, or done automatically when calling initheader().
		This creates a serializer (_ser) and de-serializer (_deser) for converting frames to bytes/ints and vice versa.
		"""

		# Get channel indices
		mychans = self.channels

		# Get channel objects
		chans = [self.wiff.channels[_] for _ in mychans]

		# Expand to full bytes
		chan_size = [c.bit.val + (c.bit.val%8) for c in chans]
		chan_size = [_//8 for _ in chan_size]
		self._frame_size = sum(chan_size)

		# Evaluate if able to use struct to parse bytes or if must step manually.
		allsane = True
		structstr = "<"
		for chan in chan_size:
			if chan == 1: structstr += "B"
			elif chan == 2: structstr += "H"
			elif chan == 4: structstr += "I"
			elif chan == 8: structstr += "Q"
			else:
				allsane = False
				break

		if allsane:
			# All channel sizes are sane struct sizes (1, 2, 4, or 8 bytes each)
			# Form a struct object with string parsed once and used for both ser and deser
			s = struct.Struct(structstr)
			def sane_ser(*samps, _s=s):
				return _s.pack(*samps)
			def sane_deser(dat, _s=s):
				return _s.unpack(dat)

			self._ser = sane_ser
			self._deser = sane_deser
		else:
			# Non-sane sizes (at least one channel is not 1, 2, 4, or 8 bytes in size)
			# Have to manually step through and parse the bytes (can't use struct library)
			def insane_ser(samps, chans=chan_size):
				ret = []
				for i in range(len(chans)):
					ret.append( samps[i].to_bytes(chans[i], byteorder='little') )
				return b''.join(ret)
			def insane_deser(dat, chans=chan_size):
				ret = []
				off = 0
				for i in range(len(chans)):
					ret.append( int.from_bytes(dat[off:off+chans[i]], byteorder='little') )
					off += chans[i]
				return tuple(ret)

			self._ser = insane_ser
			self._deser = insane_deser

	def initchunk(self, compression, segmentid):
		"""
		Initiailizes a new chunk for this chunk type.
		"""

		self.chunk.magic = 'WIFFWAVE'
		self.chunk.size = 4096
		self.chunk.attributes = (0,0,0,0, 0,0,0,0)

		attrs = [0]*8
		if compression is None:
			attrs[0] = ord('0')
		elif compression.lower() == 'z':
			attrs[0] = ord('Z')
		elif compression.lower() == 'b':
			attrs[0] = ord('B')
		else:
			raise ValueError('Unrecognized comppression type "%s"' % compression)

		attrs[4:8] = list(memoryview(struct.pack("<I", segmentid)))

		self.chunk.attributes = tuple(attrs)

	def initheader(self, channels, fidx_start, fidx_end):
		"""
		Initialize a new header
		"""

		chans_nums = []
		chans_structs = []
		for c in channels:
			if isinstance(c, int):
				chans_nums.append(c)
				chans_structs.append( self.wiff.channels[c] )
			elif isinstance(c, channel_struct):
				chans_nums.append(c.index.val)
				chans_structs.append(c)
			else:
				raise TypeError("Unknown channel type provided: '%s'" % type(c))

		# Get just the indices
		indices = chans_nums
		# Make a bitfield of it
		b = bitfield()
		# Make 256 bits wide
		b.clear(255)
		b.set(*indices)
		bs = b.to_bytes()

		self.channels = bs
		self.fidx_start = fidx_start
		self.fidx_end = fidx_end

		# Expand to full bytes and check they match data size
		chan_size = [c.bit.val + (c.bit.val%8) for c in chans_structs]

		# Total byte size of a frame
		frame_size = sum(chan_size)//8

		# Set frame size
		self._s.records.size = frame_size

		self.setup()

	@property
	def magic(self): return self.chunk.magic

	@property
	def channels(self):
		b = bitfield.from_bytes(self._s.channels[0:32])
		return b.set_indices()

	@channels.setter
	def channels(self, v):
		if isinstance(v, tuple):
			self._s.channels[0:32] = v
		elif isinstance(v, bytes):
			self._s.channels[0:32] = v
		else:
			raise TypeError("Unsupported type: '%s'" % type(v))

	@property
	def fidx_start(self): return self._s.fidx_start.val
	@fidx_start.setter
	def fidx_start(self, v):
		self._s.fidx_start.val = v

		# Copy to WIFF
		fs = self.wiff._chunks['INFO'].files
		for f in fs:
			if f.name.val == self.fw.fname:
				# only update if start is earlier
				# Eg, adding a second segment to the same file has a different
				# start frame index, so don't update if larger than the existing frame index
				if v < f.fidx_start.val:
					f.fidx_start.val = v
				return

		raise IndexError("File not found by name '%s'" % self.fw.fname)

	@property
	def fidx_end(self): return self._s.fidx_end.val
	@fidx_end.setter
	def fidx_end(self, v):
		self._s.fidx_end.val = v

		# Copy to WIFF
		fs = self.wiff._chunks['INFO'].files
		for f in fs:
			if f.name.val == self.fw.fname:
				f.fidx_end.val = v
				return

		raise IndexError("File not found by name '%s'" % self.fw.fname)

	@property
	def fidx(self): return bstruct.interval(self.fidx_start, self.fidx_end)

	def __getitem__(self, index):
		return self._s.records[index]

	@property
	def Ser(self):
		if self._ser is None: self.setup()
		return self._ser

	@property
	def DeSer(self):
		if self._deser is None: self.setup()
		return self._deser

	@property
	def channel_sizes(self):
		"""
		Get sizes of the channels as a tuple of full bytes.
		"""
		chans = self.channels

		# Get channel objects
		chans = [self.wiff.channels[_] for _ in chans]

		# Expand to full bytes and check they match data size
		return tuple([c.bit.val + (c.bit.val%8) for c in chans])

	@property
	def frame_size(self):
		"""
		Get the size of a frame in bytes.
		"""

		# Total byte size of a frame
		return sum(self.channel_sizes)//8

	@property
	def frame_space(self):
		"""
		Return the number of frames available for the currently defined space.
		This number has nothing to do with the number of frames in the chunk, only total space available to them.
		"""
		# Chunk size includes chunk header, WIFFWAVE header, and all the frames
		chunksz = self.chunk.size
		# Frame size that includes all channels
		fsz = self.frame_size
		# Chunk header size
		headersz = self._s.offset - self.chunk.offset
		# WIFFWAVE header size
		waveheadersz = self._s.lenplan(0,0)

		# Chunk size minus chunk header size minus wave header size is space available to frames
		fspace = chunksz - headersz - waveheadersz

		# Total space left for frames divided by frame size (integer devision rounds to # of full frames in the space)
		return fspace // fsz

	@frame_space.setter
	def frame_space(self, val):
		"""
		Set the total number of frames possible to store in this chunk.
		This will round up to a full 4096 page for the chunk so the actual number of space may be equal or larger than @val.
		"""
		cur = self.frame_space
		if cur == val:
			# NOP: rare case requested frame space is what's already present
			return
		elif val < cur:
			raise ValueError("Cannot shrink chunk size (currently %d, requested %d)" % (cur, val))


		# Frame size that includes all channels
		fsz = self.frame_size
		new_frames_sz = val * fsz

		# Get number of 4096 pages
		z = divmod(new_frames_sz, 4096)
		if z[1] != 0:
			# If a partial page, then incremeent to a full page
			pgs = z[0] + 1
		else:
			# Requested just the right number of frames to fill a full page (kudos)
			pgs = z[0]

		# Get new chunk size in bytes (4096 bytes per page)
		new_size = pgs * 4096

		# Actually resize the chunk
		WIFF_chunk.ResizeChunk(self.chunk, new_size)

	@property
	def frame_space_available(self):
		"""
		Return the number of available frames that can be put in the remaining space.
		"""
		# Numer of total frames available less number of frames present is the number of frames available
		return self.frame_space - self.fidx.len


	def add_frame(self, *samps):
		"""
		Add a frame of samples to the current segment.
		This updates the frame index counters and number of frames.
		"""
		return self.add_frames(samps)

	def add_frames(self, *frames):
		"""
		Add a set of frames
		"""

		if self.frame_space_available < len(frames):
			raise NeedResizeException("Cannot add frames, not enough space")

		chans = self.channels
		len_chans = len(chans)

		for i in range(len(frames)):
			if len(frames[i]) != len_chans:
				raise ValueError("Mismatch between samples (%d) and number of channels (%d) for frame %d" % (len(frames[i]),len_chans,i))

		# Get channel objects
		chans = [self.wiff.channels[_] for _ in chans]

		# Expand to full bytes and check they match data size
		chan_size = [c.bit.val + (c.bit.val%8) for c in chans]
		for j in range(len(frames)):
			samps = frames[j]
			for i in range(len(samps)):
				if chan_size[i] != len(samps[i])*8:
					raise ValueError("Sample %d for channel %d is %d bytes but channel is %d bytes (%d bits)" % (j,chans[i].index, len(samps[i]), chan_size[i], chans[i].bit))

		# Total byte size of a frame
		frame_size = sum(chan_size)//8


		# Map frame into data block
		s = self.fidx_start
		e = self.fidx_end
		delta = e - s


		# Determine frame number for next frame-to-be-added
		frame_num = self.wiff.num_frames

		# Edge case of no frames, thus s == 0, e == 0, delta == 0
		# and with 1 frame thus s == 0, e == 0, delta == 0 and frame 1 overwrites frames 0
		# The differentiating factor between these cases is that num_frames is non-zero

		for i in range(len(frames)):
			samps = frames[i]

			# Assign frame
			self._s.records[delta+i] = b''.join(samps)

		# If this is the first frame, then need to set the start
		if frame_num == 0:
			self.fidx_start = frame_num

		# Add number of frames to the end
		self.fidx_end = frame_num + len(frames)

		# Increment
		self.wiff.num_frames = frame_num + len(frames)

