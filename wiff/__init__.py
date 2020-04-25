"""
WIFF -- Waveform Interchange File Format

This is a combination of files that are similar to the generic EA IFF 85 chunk format.
However, IFF is limited to 32-bit chunk lengths which is inadequate.

The same chunk format is used for a couple types of files:
	- Informative that contains information about the entire dataset
	- Waveform files to permit slicing up large datasets into multiple files
	- Annotation files to add markers at various frames in the files

Terminology
* A recording is the entirety of recorded data with a specified number of channels and specified number of frames of data
* A frame consists of samples across all present channels at a given point in time
* A channel is a specific binary data source of data that is piece-wise present (not present sample-by-sample, but over a continous time period)
* Time index is the index into the frames from zero (start of recording) to N (last frame of the recording)
* An annotation is a marker associated to a frame or frames that gives meaning beyond the raw binary data; interpretive information

Assumptions
* Each channel has a fixed bit size and does not change throughout the recording
* Fixed number of channels throughout the recording
* Sampling rate is fixed throughout the recording and across channels
* Not all channels are required to be recorded at a given time, but different WIFFWAVE chunks are needed
  at boundaries where channel presence changes
* Essentially no limit on duration of recording; entire recording can span any number of files
  effectively limited by the WIFFWAVE.ChunkID 32-bit unique ID and 64-bit size of chunks
* Max 255 channels supported (8-bit index) but not unreasonable to support 16-bit indices
* Annotations are supported that can mark a specific frame, or range of frames


WIFF chunk format
	Offset	Length	Contents
	0		8		Chunk ID in ASCII characters
	8		8		Size of chunk not including the header
	16		8		Attribute flags unique to each chunk that can be used as needed
					Could be 32 one-bit flags, or 8 unsigned bytes, or whatever
					Regardless, all chunks have these 8 attribute bytes.
	24		N		Binary data
	Zero padding bytes to make entire chunk to be a multiple of 8

Chunks
	WIFFINFO -- Information
	Attributes
		[0] -- Version of WIFF
		[1-7] -- Reserved

	Info chunk that is used to coordinate high-level information.

	Data
		[0:1] -- Byte index of start time string
		[2:3] -- Byte index of end time string
		[4:5] -- Byte index of description
		[6:7] -- Byte index of channel definitions (X)
		[8:9] -- Byte index of files start (Y)
		[10:11] -- Byte index of files end (Z)
		[12:13] -- 16-bit sampling rate in samples per second
		[14:15] -- Number of channels (max 256 supported)
		[16:17] -- Number of files
		[18:X-1] -- Start of string data for above
		[X:Y-1] -- Start of channel definitions as non-padded sequences of the definition below
		[Y:Z] -- Start of file definitions as non-padded sequences of the definition below

		Thus, the indices of the strings' start and end can be calculated and the total size of the data block determined without having to parse actual content data (total size is in [8:9]). Strings are NOT null terminated.


	Channel definition:
		[0:1] -- Byte index of name of channel string
		[2] -- Size of samples in bits (actual storage space are upper-bit padded full bytes)
		[3:4] -- Byte index of physical units string
		[5:6] -- Byte index of comments string start
		[7:8] -- Byte index of comments string end (X)
		[9:X] -- Strings

		Channel definitions are in sequance right after each other, and so [X+1] marks the start of the next channel definition (if not the last channel).

	File definitions:
		[0:1] -- Byte index of file name string start
		[2:3] -- Byte index of file name string end (X)
		[4:11] -- Start frame index
		[12:19] -- End frame index (inclusive)
		[20:X] -- File name string


	WIFFWAVE -- Waveform data
	Attributes
		[0] -- First byte is an ASCII character indicating compression used
			0			No compression
			Z			zlib
			B			bzip2
		[1] -- Reserved
		[2] -- Reserved
		[3] -- Reserved
		[4:7] -- 32 bit chunk ID references in WIFFINFO to order the chunks
				 Chunk ID's need not be in numerical order, only unique within the same WIFF data set.

	If compression is used, the entire data block, except padding bytes, are decompressed first.

	Data
		[0:7] -- Bitfield identifying which channels are present from 0 to 255
		[8:15] -- First frame index
		[16:23] -- Last frame index
		[24:X] -- Frames




	WIFFANNO -- Annotations
		[0] -- First byte is an ASCII character indicating compression used
			0			No compression
			Z			zlib
			B			bzip2

	If compression is used, the entire data block, except padding bytes, are decompressed first.

	Annotations



"""

import copy
import datetime
import json
import os.path

import funpack

from .compress import WIFFCompress

DATE_FMT = "%Y%m%d %H%M%S.%f"
WIFF_VERSION = 1

class WIFF:
	def __init__(self, fname, props=None):
		# f is the WAVEINFO file
		self.f = None

		# List of files containing WIFFWAVE chunks
		self._files = []

		if os.path.exists(fname):
			self._open_existing(fname)
		else:
			self._open_new(fname, props)

	@property
	def fs(self): return self._props['fs']
	@fs.setter
	def fs(self, v): self._props['fs'] = v

	@property
	def start(self): return self._props['start']
	@start.setter
	def start(self, v): self._props['start'] = v

	@property
	def end(self): return self._props['end']
	@end.setter
	def end(self, v): self._props['end'] = v

	@property
	def description(self): return self._props['description']
	@description.setter
	def description(self, v): self._props['description'] = v

	@property
	def channels(self):
		return WIFF_channels(self._props['channels'])

	@property
	def files(self):
		return copy.deepcopy(self._props['files'])


	def __enter__(self):
		return self

	def __exit__(self, *exc):
		self.close()
		return False

	def close(self):
		""" Close """
		if self._f:
			self._f.close()
			self._f = None

	def _open_existing(self, fname):
		self._f = open(fname, 'rb')

		self._chunks = []

		chunks = _WIFF_file.FindChunks(self._f)
		for chunk in chunks:
			if chunk['magic'] == 'WIFFINFO':
				self._f.seek(chunk['offset data'])
				dat = self._f.read(chunk['size'])

				props = _WIFFINFO_header.DeSer(dat)

				self._chunks.append({
					'file': fname,
					'magic': chunk['magic'],
					'size': chunk['size'],
					'offset header': chunk['offset header'],
					'offset data': chunk['offset data'],
					'_attrs': chunk['attrs'],
					'attrs': {
						'version': chunk['attrs'][0],
					},
				})
				self._props = props
			else:
				raise NotImplementedError


	def _open_new(self, fname, props):
		self._f = open(fname, 'wb')

		start = props['start'].strftime(DATE_FMT)
		end = props['end'].strftime(DATE_FMT)

		d = _WIFFINFO_header.Ser(start, end, props['description'], props['fs'], props['channels'], props['files'])

		h = _WIFF_file.Ser('WIFFINFO', len(d), (1,0,0,0,0,0,0,0))

		self._f.write(h)
		self._f.write(d)
		self._f.close()

		# Now open as existing
		self._open_existing(fname)

	def dumps_dict(self):
		"""
		Dump WIFF meta data into a dict() for handling within Python.
		"""
		raise NotImplementedError

	def dumps_str(self):
		"""
		Dump WIFF meta data into a string that can be printed.
		"""

		d = self.dumps_dict()

		raise NotImplementedError

	def dumps_json(self):
		"""
		Dump WIFF meta data into a json for handling within Python.
		"""

		return json.dumps(self.dumps_dict())

class WIFF_channels:
	"""
	Simple wrapper class to the channels.
	Implements the item getter pattern that returns WIFF_channel instances that then
	 permits getting and setting channel properties.
	"""

	def __init__(self, channels):
		self._channels = channels

	def __getitem__(self, idx):
		# Throw error if bad index
		if type(idx) == slice:
			items = self._channels[idx]
			return [WIFF_channel(item['index'], self._channels) for item in items]
		else:
			x = self._channels[idx]
			return WIFF_channel(idx, self._channels)

	def __len__(self):
		return len(self._channels)

	def __repr__(self):
		return "<WIFF_channels count=%d>" % len(self)

class WIFF_channel:
	"""
	Simple wrapper around channel dictionary.
	Permits getting and setting channel properties.
	"""

	def __init__(self, index, channels):
		self._index = index
		self._channels = channels

	def __repr__(self):
		return "<WIFF_channel i=%d name='%s' bit=%d unit='%s' comment='%s'>" % (self._index, self.name, self.bit, self.unit, self.comment)

	@property
	def name(self): return self._channels[self._index]['name']
	@name.setter
	def name(self, v): self._channels[self._index]['name'] = v

	@property
	def bit(self): return self._channels[self._index]['bit']
	@bit.setter
	def bit(self, v): self._channels[self._index]['bit'] = v

	@property
	def unit(self): return self._channels[self._index]['unit']
	@unit.setter
	def unit(self, v): self._channels[self._index]['unit'] = v

	@property
	def comment(self): return self._channels[self._index]['comment']
	@comment.setter
	def comment(self, v): self._channels[self._index]['comment'] = v



class _WIFF_file:
	@classmethod
	def FindChunks(cls, f):
		sz = os.path.getsize(f.name)

		chunks = []

		off = 0
		while off < sz:
			f.seek(off)
			head = f.read(24)
			p = cls.DeSer(head)

			# Include offsets
			p['offset header'] = off
			p['offset data'] = off + 24

			chunks.append(p)
			off += p['size'] + 24 # Add header size

		return chunks

	@classmethod
	def Ser(cls, magic, size, attrs):
		fp = funpack.fpack(endian=funpack.Endianness.Big)
		fp.string_ascii(magic)
		fp.u64(size)
		fp.u8(*attrs)

		return fp.Data

	@classmethod
	def DeSer(cls, dat):
		fup = funpack.funpack(dat, endian=funpack.Endianness.Big)

		magic = fup.string_ascii(8)
		size = fup.u64()
		attrs = fup.u8(8)

		return {'magic': magic, 'size': size, 'attrs': attrs}

class _WIFFINFO_header:
	@classmethod
	def Ser(cls, start, end, desc, fsamp, chans, files):
		b_start = start.encode('utf8')
		b_end = end.encode('utf8')
		b_desc = desc.encode('utf8')

		fp = funpack.fpack(endian=funpack.Endianness.Big)

		# Start time at 18
		idx = 18
		fp.u16(idx)
		idx += len(b_start)

		# End time
		fp.u16(idx)
		idx += len(b_end)

		# Description
		fp.u16(idx)
		idx += len(b_desc)

		# Start of chennel descriptions
		fp.u16(idx)

		# Start offset for channel descriptions
		chanidx = idx

		fz = funpack.fpack(endian=funpack.Endianness.Big)
		for chan in chans:
			b_name = chan['name'].encode('utf8')
			b_unit = chan['unit'].encode('utf8')
			b_comment = chan['comment'].encode('utf8')

			# Channel name at 9
			chanidx += 9
			fz.u16(chanidx)
			chanidx += len(b_name)

			# Sample bit depth
			fz.u8(chan['bit'])

			# Physical units
			fz.u16(chanidx)
			chanidx += len(b_unit)

			# Comment
			fz.u16(chanidx)
			chanidx += len(b_comment)

			# End of strings
			fz.u16(chanidx-1)

			fz.bytes(b_name)
			fz.bytes(b_unit)
			fz.bytes(b_comment)

		fileidx = chanidx

		ff = funpack.fpack(endian=funpack.Endianness.Big)
		for fs in files:
			b_name = fs['name'].encode('utf8')

			# File name at 20
			fileidx += 20
			ff.u16(fileidx)
			ff.u16(fileidx + len(b_name))

			# Start and end frame index
			ff.u64(fs['start'])
			ff.u64(fs['end'])

			# File name
			ff.bytes(b_name)
			fileidx += len(b_name)

		# Start of files
		fp.u16(chanidx-1)

		# End of files
		fp.u16(fileidx-1)

		# Sampling rate
		fp.u16(fsamp)

		# Number of channels
		fp.u16(len(chans))

		# Number of files
		fp.u16(len(files))

		# Add in strings
		fp.bytes(b_start)
		fp.bytes(b_end)
		fp.bytes(b_desc)

		# Add in channel data
		fp.bytes(fz.Data)

		# Add in files data
		fp.bytes(ff.Data)

		return fp.Data

	@classmethod
	def DeSer(cls, dat):
		fup = funpack.funpack(dat, endian=funpack.Endianness.Big)

		idx_start = fup.u16()
		idx_end = fup.u16()
		idx_desc = fup.u16()
		idx_chan = fup.u16()
		idx_files = fup.u16()
		idx__END__ = fup.u16()
		fs = fup.u16()
		num_chan = fup.u16()
		num_files = fup.u16()

		s_start = fup.string_utf8(idx_end - idx_start)
		s_end = fup.string_utf8(idx_desc - idx_end)
		s_desc = fup.string_utf8(idx_chan - idx_desc)

		props = {
			'start': datetime.datetime.strptime(s_start, DATE_FMT),
			'end': datetime.datetime.strptime(s_end, DATE_FMT),
			'description': s_desc,
			'fs': fs,
			'channels': [],
			'files': [],
		}

		for i in range(num_chan):
			idx_name = fup.u16()
			bits = fup.u8()
			idx_unit = fup.u16()
			idx_comment = fup.u16()
			idx__END__ = fup.u16()

			c = {
				'index': i,
				'name': fup.string_utf8(idx_unit - idx_name),
				'bit': bits,
				'unit': fup.string_utf8(idx_comment - idx_unit),
				'comment': fup.string_utf8(idx__END__+1 - idx_comment),
			}
			props['channels'].append(c)

		for i in range(num_files):
			idx_name = fup.u16()
			idx__END__ = fup.u16()
			fidx_start = fup.u64()
			fidx_end = fup.u64()

			f = {
				'index': i,
				'name': fup.string_utf8(idx__END__ - idx_name),
				'start': fidx_start,
				'end': fidx_end,
			}
			props['files'].append(f)

		return props

