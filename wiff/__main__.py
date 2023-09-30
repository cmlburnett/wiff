import argparse
import os

import wiff
import funpack

def _main():
	p = argparse.ArgumentParser()
	p.add_argument('--info', action='store_true', help="Print information about the WIFF file")
	p.add_argument('--dumpdata', choices=['csv'], help="Dump data from the WIFF")
	p.add_argument('FILE', nargs=1, help="File to analyze")

	args = p.parse_args()

	if args.info:
		_main_info(args)
	elif args.dumpdata is not False:
		_main_dumpdata(args)

def _main_info(args):
	w = wiff.open(args.FILE[0])

	s = os.stat(args.FILE[0])
	
	vals = []
	vals.append( ('Filename', args.FILE[0]) )
	vals.append( ('Size', str(s.st_size)) )
	vals.append( (None,None) )


	print("  ---------- File Information ----------")
	print_2col(vals)


	vals = []
	for i in w.meta:
		m = w.meta[i]
		vals.append( (m.key, m.value) )

	print("  ---------- Meta values ----------")
	print_2col(vals)



	for i in w.recording:
		r = w.recording[i]

		vals = []
		vals.append( ('Start', r.start) )
		vals.append( ('End', r.end) )
		vals.append( ('Description', r.description) )
		vals.append( ('Sampling Rate', r.sampling) )
		vals.append( ('# Channels', len(r.channel)) )
		vals.append( ('Frame Start', r.frame_table.fidx_start) )
		vals.append( ('Frame End', r.frame_table.fidx_end) )

		print()
		print("  ---------- Recording #%d ----------" % i)
		print_2col(vals)

	for i in w.channel:
		c = w.channel[i]

		vals = []
		vals.append( ("Index", c.idx) )
		vals.append( ("Name", c.name) )
		vals.append( ("Bits", c.bits) )
		vals.append( ("Unit", c.unit) )
		vals.append( ("Storage", c.storage) )
		vals.append( ("Comment", c.comment) )
		print()
		print("  ---------- Channel #%d ----------" % i)
		print_2col(vals)

	for i in w.segment:
		s = w.segment[i]
		vals = []
		vals.append( ('Recording', s.id_recording) )
		vals.append( ('Frame Start', s.fidx_start) )
		vals.append( ('Frame End', s.fidx_end) )
		vals.append( ('Channels', ",".join([str(_.channel.idx) for _ in s.channelset])) )
		vals.append( ('Stride', s.stride) )
		vals.append( ('Blob', s.id_blob) )

		print()
		print("  ---------- Segment #%d ----------" % i)
		print_2col(vals)

	for i in w.blob:
		b = w.blob[i]
		vals = []
		vals.append( ('Compression', b.compression) )
		vals.append( ('Data size', len(b.data)) )

		print()
		print("  ---------- Blob #%d ----------" % i)
		print_2col(vals)

	for i in w.annotation:
		a = w.annotation[i]
		vals = []
		vals.append( ('Recording', a.id_recording) )
		vals.append( ('Frame Start', a.fidx_start) )
		vals.append( ('Frame End', a.fidx_end) )
		vals.append( ('Type', a.type) )

		if a.type == 'C':
			vals.append( ('Comment', a.comment) )
		elif a.type == 'M':
			vals.append( ('Marker', a.marker) )
		elif a.type == 'D':
			vals.append( ('Marker', a.marker) )
			vals.append( ('Data', a.data) )
		else:
			print("Unknown annotation: %s" % str(a))

		print()
		print("  ---------- Annotation #%d ----------" % i)
		print_2col(vals)

def _main_dumpdata(args):
	w = wiff.open(args.FILE[0])

	print("# File=%s" % args.FILE[0])
	for i in w.meta:
		m = w.meta[i]
		print("# %s=%s" % (m.key, m.value))

	for i in w.recording:
		r = w.recording[i]
		print("# Recording %d" % i)
		for j in r.segment:
			s = r.segment[j]
			cset = s.channelset
			chans = [_.channel for _ in cset]
			b = s.blob

			if b.compression is not None:
				raise Exception("Unable to handle compression '%s' on segment %d" % (b.compression, j))

			for x in range(s.fidx_end - s.fidx_start):
				off = s.stride * x
				f = funpack.funpack(b.data[off:off+s.stride], 'little')
				for c in chans:
					if c.storage == 1:
						print(f.u8())
					elif c.storage == 2:
						print(f.u16())
					elif c.storage == 4:
						print(f.u32())
					elif c.storage == 8:
						print(f.u64())
					else:
						raise NotImplemented("Unable to handle storage of %d bytes" % c.storage)


def print_2col(vals):
	keys,values = zip(*vals)
	len_keys = max([len(_) for _ in keys if _ is not None])
	len_keys += 5

	for i,key in enumerate(keys):
		if key is None:
			print()
			continue

		print( "%{0}s: {1}".format(len_keys, values[i]) % key )


if __name__ == '__main__':
	_main()

