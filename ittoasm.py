import argparse, math

parser = argparse.ArgumentParser(description='Converts .it module to pokecrystal asm')
parser.add_argument('-red', action='store_const', const=True, default=False, help='produces pokered asm instead')
parser.add_argument('fi', metavar='I', type=argparse.FileType('rb'), help='Input file name')
parser.add_argument('fo', metavar='O', type=argparse.FileType('wb'), help='Output file name')
nsp = parser.parse_args()

class Inst:
	duty = 0
	vibr = 0
	ntty = 0
	
	def __init__(self, a, b, c):
		self.duty = a
		self.ntty = b
		self.vibr = c

def le16(a): return ord(a.read(1)) + (ord(a.read(1)) << 8)
def le32(a): return le16(a) + (le16(a) << 16)
def cals(a, b):
	s = a * 2
	t = b
	if(s > 15):
		d = int(math.floor(s/16))
		s = int(s / d) * 2
		t = int(t / d)
	t = int(19200 / t)
	return s, t

def calp(a):
	if a < 22: return 0xf0
	elif a < 43: return 0xff
	return 0xf

fin = nsp.fi
fou = nsp.fo
red = nsp.red
if fin.read(4) != "IMPM": raise Exception("Invalid magic number. This is not .it module file!")

name = fin.read(26).strip(chr(0))
if name == "": name = fin.name
tpb = ord(fin.read(1))
tpm = ord(fin.read(1))
onum = le16(fin)
inum = le16(fin)
snum = le16(fin)
pnum = le16(fin)

fin.seek(0x32, 0)
spe = ord(fin.read(1))
tem = ord(fin.read(1))
spea, tema = cals(spe, tem)

fin.seek(0x36, 0)
msglen = le16(fin) - 1
fin.seek(le32(fin), 0)

print "Converting {} into pokecrystal asm...".format(name)

if msglen != -1:
	msg = fin.read(msglen).replace(chr(0xd), '\n')
	print "===================="
	print msg
	print "===================="

print "{} instruments, {} samples, {} patterns and {} patterns long.".format(inum, snum, pnum, onum - 1)
print "[Initial] Speed {} | Tempo {} -> Speed {} | Tempo {} (asm)".format(spe, tem, spea, tema)

fin.seek(0x40, 0)
panl = []
for i in range(64): panl.append(calp(ord(fin.read(1))))

fin.seek(0xc0, 0)
ords = ""
ordl = []
inspl = []
patpl = []
for d in range(onum - 1):
	cpat = ord(fin.read(1))
	if cpat != 254:
		ords = ords + str(cpat) + " "
		ordl.append(cpat)
print "Pattern order: {}".format(ords)

fin.seek(0xc0 + onum, 0)
for d in range(inum): inspl.append(le32(fin))
fin.seek(snum * 4, 1)
for d in range(pnum): patpl.append(le32(fin))

print ""
print "## Instruments ##"
print ""

insl = []
c = 0
for insp in inspl:
	fin.seek(insp + 0x20, 0)
	inam = fin.read(26).strip(chr(0)).split('|')
	d = 2
	n = 0xa7
	v = 0
	try:
		dn = int(inam[0], base=16)
		d = (dn >> 8) & 3
		n = dn & 255
	except ValueError:
		print "Invalid note type for instrument #{}, defaulting duty to 2 and notetype to a7...".format(c)
	if(len(inam) > 1):
		try:
			v = int(inam[1], base=16) & 0xffff
		except ValueError:
			print "Invalid vibrato for instrument #{}, defaulting to 0...".format(c)
	insl.append(Inst(d,n,v))
	print "#{:<3}: Duty {:x}, Note Type {:02x}, Vibrato {:04x}".format(c, d, n, v)
	c = c + 1
	
print ""
print "Converting pattern data..."

chdat = {}
ntLUT = ['C_', 'C#', 'D_', 'D#', 'E_', 'F_', 'F#', 'G_', 'G#', 'A_', 'A#', 'B_']
ch4LUT = ["snare1","snare2","snare3","snare4","snare5","triangle1","triangle2",
          "snare6","snare7","snare8","snare9","cymbal1","cymbal2","cymbal3",
		  "mutedsnare1","triangle3","mutedsnare2","mutedsnare3","mutedsnare4"]
nlc = {}
oct = {}
cins = {}
cnt = {}
cnta = -1
instxt = {}
nttxt = {}
mv = {}
efftxt = {}
patf = {}

def tx_note(ch,a):
	if ch == 4:
		if red: return "\t{}".format(ch4LUT[(oct[ch]-4)*12+a])
		else: return "\tnote {}".format(ntLUT[a])
	else:
		if red: return "\t{}".format(ntLUT[a])
		else: return "\tnote {}".format(ntLUT[a])
	
def tx_rest():
	if red: return "\trest"
	else: return "\tnote __"
	
def tx_nlc(a):
	if red: return " {}\n".format(nlc[a])
	else: return ", {}\n".format(nlc[a])
	
def tx_ntty(ch,a):
	if ch == 4:
		if red: return "\tdspeed ${:x}\n".format(spea)
		else: return "\tnotetype ${:x}\n".format(spea)
	else:
		if red: return "\tnotetype ${:x}, ${:x}, ${:x}\n".format(spea, (a >> 4) & 15, a & 15)
		else: return "\tnotetype ${:x}, ${:x}\n".format(spea, a)
	
def tx_inte(ch,a):
	if red: return tx_ntty(ch,a)
	else: return "\tintensity ${:x}\n".format(a)
	
def tx_vibr(a):
	if red: return "\tvibrato ${:x}, ${:x}, ${:x}\n".format((a >> 8) & 255, (a >> 4) & 15, a & 15)
	else: return "\tvibrato ${:x}, ${:x}\n".format((a >> 8) & 255, a & 255)
	
def tx_duty(ch,a):
	if ch > 2: return "" # Wave channel and noise channel don't have duty cycle
	if red: return "\tduty ${:x}\n".format(a)
	else: return "\tdutycycle ${:x}\n".format(a)
	
def tx_pan(a):
	if red: return "" # stereo panning is not recommended in Gen 1
	else: return "\tstereopanning ${:x}\n".format(a)

for pat in ordl:
	for k in patf.keys(): patf[k] = True
	fin.seek(patpl[pat] + 2, 0)
	rows = le16(fin)
	crow = 0
	fin.seek(4, 1)
	while crow < rows:
		chv = ord(fin.read(1))
		ch = chv & 63
		if chv == 0:
			for k in nlc.keys():
				if nlc[k] == 16:
					if cnt[k] >= 254: nttxt[k] = nttxt[k] + tx_nlc(k) + tx_rest()
					else: nttxt[k] = nttxt[k] + tx_nlc(k) + tx_note(k,cnt[k])
					nlc[k] = 0
				nlc[k] = nlc[k] + 1
			crow = crow + 1
			efftxt[ch] = ""
		else:
			if chv & 128: mv[ch] = ord(fin.read(1))
			if ch not in oct.keys(): oct[ch] = -2
			if ch not in nttxt.keys(): nttxt[ch] = ""
			if ch not in instxt.keys(): instxt[ch] = ""
			if ch not in efftxt.keys(): efftxt[ch] = ""
			if ch not in chdat.keys(): 
				chdat[ch] = "; Pat {} Row {}\n".format(pat, crow)
				patf[ch] = False
			if ch not in cnt.keys(): cnt[ch] = -1
			if mv[ch] & 1:
				if ch in nlc.keys():
					chdat[ch] = chdat[ch] + efftxt[ch] + instxt[ch] + nttxt[ch] + tx_nlc(ch)
					if patf[ch]: chdat[ch] = chdat[ch] + "; Pat {} Row {}\n".format(pat, crow)
					patf[ch] = False
					nttxt[ch] = ""
					instxt[ch] = ""
					efftxt[ch] = ""
				nlc[ch] = 0
				nt = ord(fin.read(1))
				if nt >= 254: nttxt[ch] = nttxt[ch] + tx_rest()
				else:
					noct = int(nt / 12) - 1
					if noct != oct[ch]:
						oct[ch] = noct
						if ch != 4: nttxt[ch] = nttxt[ch] + "\toctave {}\n".format(oct[ch])
					nt = nt % 12
					nttxt[ch] = nttxt[ch] + tx_note(ch,nt)
				cnt[ch] = nt
			if mv[ch] & 2:
				nins = ord(fin.read(1)) - 1
				nind = insl[nins].duty
				ninn = insl[nins].ntty
				ninv = insl[nins].vibr
				if ch not in cins.keys():
					if ch == 1: instxti = "\ttempo ${:x}\n{}{}".format(tema, tx_duty(ch,nind), tx_ntty(ch,ninn))
					else: instxti = "{}{}".format(tx_duty(ch,nind), tx_ntty(ch,ninn)) # tempo command is global
					if ch == 4 and not red: instxti = "{}\ttogglenoise ${}\n".format(instxti,ninn&15)
					if ninv != 0: instxti = instxti + tx_vibr(ninv)
					instxti = instxti + tx_pan(panl[ch-1])
					chdat[ch] = chdat[ch] + instxti
					instxt[ch] = ""
				elif nins != cins[ch]:
					if nind != insl[cins[ch]].duty: instxt[ch] = instxt[ch] + tx_duty(ch,nind)
					if ninn != insl[cins[ch]].ntty: instxt[ch] = instxt[ch] + tx_inte(ch,ninn)
					if ninv != insl[cins[ch]].vibr: instxt[ch] = instxt[ch] + tx_vibr(ninv)
				cins[ch] = nins
				
				if nlc[ch] != 0:
					chdat[ch] = chdat[ch] + efftxt[ch] + nttxt[ch] + tx_nlc(ch) + instxt[ch]
					instxt[ch] = ""
					efftxt[ch] = ""
					if patf[ch]: chdat[ch] = chdat[ch] + "; Pat {} Row {}\n".format(pat, crow)
					patf[ch] = False
					if cnt[ch] >= 254: nttxt[ch] = tx_rest()
					else: nttxt[ch] = tx_note(ch,cnt[ch])
					nlc[ch] = 0
			if mv[ch] & 4: fin.seek(1, 1)
			if mv[ch] & 8:
				efftxt[ch] = ""
				eff = ord(fin.read(1))
				effv = ord(fin.read(1))
				if eff == 20: # Txx
					if effv < 0x10: effv = tema - (effv & 0xf) * (spea/2 - 1)
					elif effv < 0x20: effv = tema + (effv & 0xf) * (spea/2 - 1)
					spea, tema = cals(spea/2, effv)
					efftxt[ch] = efftxt[ch] + "\ttempo ${:x}\n".format(tema)
				if eff == 1:  # Axx
					spea, tema = cals(effv, tema)
					efftxt[ch] = efftxt[ch] + tx_ntty(ch, insl[cins[ch]].ntty)
				if eff == 19 and effv / 0x10 == 8: # S8x
					efftxt[ch] = efftxt[ch] + tx_pan(calp((effv&0xf)*63/15))
			if mv[ch] & 32 and nlc[ch] != 0:
				chdat[ch] = chdat[ch] + efftxt[ch] + nttxt[ch] + tx_nlc(ch) + instxt[ch]
				instxt[ch] = ""
				efftxt[ch] = ""
				if patf[ch]: chdat[ch] = chdat[ch] + "; Pat {} Row {}\n".format(pat, crow)
				patf[ch] = False
				if cnt[ch] >= 254: nttxt[ch] = tx_rest()
				else: nttxt[ch] = tx_note(ch,cnt[ch])
				nlc[ch] = 0

for k in chdat.keys():
	chdat[k] = chdat[k] + nttxt[k] + tx_nlc(k)
	fou.write("Ch{}:\n{}\tendchannel\n\n".format(k, chdat[k]))

fin.close()
fou.close()
print "Completed!"