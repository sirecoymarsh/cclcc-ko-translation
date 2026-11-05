"""카오스 차일드 LCC 한국어 번역 한 묶음 검사(클라우드 판).

  python3 tools/gates.py CC0001-claa01-P01 [CC0002-... ...]   묶음마다 PASS / FAIL / PARTIAL / MISSING 과 고칠 점
  python3 tools/gates.py --lane A                              갈래 A 진행 상황(통과·실패·남은 묶음)

원문 cclcc-ko-kit/원문/<묶음>.json 의 entries 와 번역 cclcc-ko-kit/번역/<묶음>.json([{"id","ko"[,"note"]}])을 대조한다.
오류(errors)는 고쳐야 통과, 참고(warnings)는 보고 맞으면 고친다. 원본은 F:\\AI\\cclcc-gemini\\tools\\gates.py(제미나이 킷)이고,
경로를 저장소 기준으로, 스위치 글꼴 글자 목록을 font_chars.json 으로, 보류 항목(ko 빈칸 + note 「보류」)을 통과로 바꿨다.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "cclcc-ko-kit"
SRC, OUT = KIT / "원문", KIT / "번역"
GLOSSARY = Path(__file__).with_name("glossary.json")
FONT = Path(__file__).with_name("font_chars.json")
JA_POLITE = re.compile(r"(です|ます|でした|ました|ません|ませんか|ください|でしょう|ですか|ますか)")
KO_POLITE = re.compile(r"(요|니다|니까|세요|십시오|죠|오)[.!?…〜~♪♥]*$")
VOICE_MIN, VOICE_SHARE = 10, 0.7
COMMA = re.compile(r"[가-힣]의, |[가-힣], 다(?=[」』.!?…\s]|$)|[가-힣], (?:를|을|는|은|에게|에서|으로|로)(?![가-힣])")
TAG = re.compile(r"⟦[^⟧]*⟧")
RUBY = re.compile(r"⟦rb⟧(.*?)⟦rt⟧(.*?)⟦/r⟧", re.S)
KANA = re.compile(r"[\u3041-\u3096\u30a1-\u30fa\u30fc\u30fd\u30fe\uff66-\uff9f]")   # ・(U+30FB) 는 허용
HANJA = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
FULLWIDTH = {"！": "!", "？": "?", "。": ".", "、": ",", "，": ",", "．": "."}
BAD_DASH = "—─－‐ー"
SHE = re.compile(r"(?<![가-힣])그녀")
HE = re.compile(r"(?<![가-힣])그(?:는|가|를|의|에게|한테)(?![가-힣])")

_src, _font = {}, None


def source(packet):
    if packet not in _src:
        _src[packet] = json.loads((SRC / (packet + ".json")).read_text("utf-8"))["entries"]
    return _src[packet]


def font():
    """번역문에 나와도 되는 한글 아닌 글자(게임 글꼴에 있는 ASCII·문장부호·기호)."""
    global _font
    if _font is None:
        _font = set(json.loads(FONT.read_text("utf-8")))
    return _font


def plain(s):
    return TAG.sub("", s).strip()


def tags_wo_ruby(s):
    return TAG.findall(RUBY.sub("", s))


def partial_rows(raw, want):
    if not raw.lstrip().startswith("["):
        return None
    ids = re.findall(r'"id"\s*:\s*"([^"]+)"', raw)
    if ids and ids == want[:len(ids)] and len(ids) < len(want):
        return ids
    return None


def last_sentence(ko):
    t = plain(ko).rstrip()
    t = re.sub(r"[」』）)]+$", "", t).rstrip()
    return t


def check(packet, out_dir=OUT):
    path = Path(out_dir) / (packet + ".json")
    if not path.exists():
        return "MISSING", [], []
    rows = source(packet)
    want = [r["id"] for r in rows]
    errors, warnings = [], []
    try:
        raw = path.read_text("utf-8-sig")
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        part = partial_rows(raw, want)
        if part is not None:
            return "PARTIAL", ["묶음을 끝까지 쓰지 않았다(%d/%d 항목). %s 다음 항목부터 이어 쓰고 배열을 ] 로 닫는다."
                               % (len(part), len(want), part[-1])], []
        near = re.findall(r'"id"\s*:\s*"([^"]+)"', raw[:e.pos])
        return "FAIL", ["JSON으로 읽을 수 없다: %d번째 줄%s에서 깨졌다(%s). 따옴표·쉼표·괄호를 맞추고 "
                        '[{"id": …, "ko": …}, …] 배열 하나로 다시 저장한다.'
                        % (e.lineno, "(%s 항목 뒤)" % near[-1] if near else "", e.msg)], []
    except Exception as e:  # noqa: BLE001
        return "FAIL", ["파일을 읽을 수 없다(%s). UTF-8 JSON 배열 하나로 다시 저장한다." % str(e)[:120]], []
    if not isinstance(result, list) or not all(isinstance(x, dict) and isinstance(x.get("id"), str)
                                               and isinstance(x.get("ko"), str) for x in result):
        return "FAIL", ['형식이 다르다. [{"id": …, "ko": …}, …] 배열 하나여야 한다(00_먼저_읽기.md 4절).'], []
    got = [x["id"] for x in result]
    if got != want:
        if len(got) != len(want):
            errors.append("항목 수가 원문 %d개와 다르다(%d개). 원문 항목마다 하나씩, 합치거나 나누거나 빼지 않는다." % (len(want), len(got)))
        first = next((n for n, (a, b) in enumerate(zip(got, want)) if a != b), min(len(got), len(want)))
        errors.append("%d번째 항목부터 id 순서가 원문과 어긋난다(원문 %s, 받은 %s)."
                      % (first + 1, want[first] if first < len(want) else "없음", got[first] if first < len(got) else "없음"))
        return "FAIL", errors, warnings
    allowed = font()
    voice, body_ko = {}, []
    for r, x in zip(rows, result):
        i, ja, ko, typ = r["id"], r["jp"], x["ko"], r["type"]
        if not plain(ko) and plain(ja):
            if "보류" in str(x.get("note", "")):
                warnings.append("%s: 보류(%s)" % (i, x.get("note")))
            else:
                errors.append("%s: 번역이 비어 있다." % i)
            continue
        if "\n" in ko or "\r" in ko:
            errors.append("%s: 실제 줄바꿈 문자가 들어갔다. 줄바꿈은 원문처럼 ⟦n⟧ 태그로만." % i)
        if r.get("speaker_ko") and plain(ko).startswith(r["speaker_ko"]):
            warnings.append("%s: 번역 앞에 화자 이름(%s)을 넣었는지 확인" % (i, r["speaker_ko"]))
        if tags_wo_ruby(ko) != tags_wo_ruby(ja):
            errors.append("%s: 태그를 원문과 같은 개수·순서로 둔다(원문 %s / 받은 %s). 루비 ⟦rb⟧⟦rt⟧⟦/r⟧ 한 벌을 통째로 빼는 것만 된다."
                          % (i, "".join(tags_wo_ruby(ja)) or "없음", "".join(tags_wo_ruby(ko)) or "없음"))
        rk, rj = RUBY.findall(ko), RUBY.findall(ja)
        if len(rk) > len(rj):
            errors.append("%s: 원문에 없는 루비를 더했다. 루비는 원문 루비 자리에만." % i)
        bare = RUBY.sub("", ko)
        if any(t in bare for t in ("⟦rb⟧", "⟦rt⟧", "⟦/r⟧")):
            errors.append("%s: 루비 꼴이 깨졌다. ⟦rb⟧밑글⟦rt⟧읽기⟦/r⟧ 셋을 한 벌로 둔다." % i)
        for base, reading in rk:
            dots = reading.replace("⟦rbc⟧", "")
            if "⟦rbc⟧" in reading and not set(dots) <= {"●"}:
                errors.append("%s: 강조점 루비(⟦rbc⟧●…)의 읽기 칸에는 ● 만 둔다(받은 「%s」). 점을 글자로 바꾸지 않는다." % (i, plain(dots)))
            elif dots and set(dots) <= {"●"}:
                n = len(re.sub(r"\s", "", plain(base)))
                if len(dots) != n:
                    errors.append("%s: 강조점 루비의 점 수(%d)를 한국어 밑글 「%s」의 글자 수(%d)에 맞춘다."
                                  % (i, len(dots), plain(base), n))
            elif plain(base) and plain(base) == plain(reading):
                warnings.append("%s: 루비 읽기가 밑글과 같다(%s) — 루비를 빼도 됨" % (i, plain(base)))
        text = TAG.sub("", ko)
        kana, hanja = sorted(set(KANA.findall(text))), sorted(set(HANJA.findall(text)))
        if kana or hanja:
            errors.append("%s: 일본어 글자 %s 를 남기지 않는다(이름·용어도 한글로, 늘임표 ー 는 모음을 늘이거나 〜, っ·ッ 는 빼거나 받침으로)."
                          % (i, "".join(kana + hanja)))
        fw = sorted({c for c in text if c in FULLWIDTH})
        if fw:
            errors.append("%s: 전각 문장부호 %s 대신 반각 %s 를 쓴다." % (i, "".join(fw), "".join(FULLWIDTH[c] for c in fw)))
        bd = sorted({c for c in text if c in BAD_DASH} - {"ー"})
        if bd:
            errors.append("%s: 줄표는 「―」(두 개 한 벌 ――)만 쓴다(받은 %s)." % (i, "".join(bd)))
        odd = sorted({c for c in text if not ("\uac00" <= c <= "\ud7a3" or "\u3131" <= c <= "\u3163")
                      and c not in allowed and not KANA.search(c) and not HANJA.search(c) and c not in FULLWIDTH and c not in BAD_DASH})
        if odd:
            errors.append("%s: 게임 글꼴에 없는 글자 %s 는 쓰지 않는다(\" → “ ” 또는 「」)." % (i, " ".join(odd)))
        if typ == "dialogue" and SHE.search(text):
            errors.append("%s: 대사에 「그녀」를 쓰지 않는다 — 이름·지시어(그 애·걔·저 사람)·생략으로." % i)
        elif typ == "dialogue" and HE.search(text):
            warnings.append("%s: 대사 속 3인칭 「%s」 확인" % (i, HE.search(text).group()))
        if typ == "dialogue" and r.get("speaker") and JA_POLITE.search(plain(ja)):
            v = voice.setdefault(r["speaker_ko"], [0, []])
            v[0] += 1
            if not KO_POLITE.search(last_sentence(ko)):
                v[1].append(i)
        if typ in ("dialogue", "narration"):
            body_ko.append(plain(ko))
            if len(plain(ko)) > max(40, 3 * len(plain(ja))):
                warnings.append("%s: 원문보다 훨씬 길다(%d → %d자)" % (i, len(plain(ja)), len(plain(ko))))
            m = COMMA.search(plain(ko))
            if m:
                warnings.append("%s: 일본어 쉼표 끊김을 옮긴 꼴(%s)" % (i, m.group()))
    for sp, (n_pol, plain_ids) in voice.items():
        if n_pol >= VOICE_MIN and len(plain_ids) >= VOICE_SHARE * n_pol:
            errors.append("%s 의 대사 %d줄 중 %d줄이 원문은 です·ます 존댓말인데 번역은 반말이다(%s 등). 03 캐릭터 보이스대로 "
                          "원문 높임에 맞춰 그 인물의 말투를 고친다." % (sp, n_pol, len(plain_ids), ", ".join(plain_ids[:4])))
    long_ko = [k for k in body_ko if len(k) >= 12]
    if long_ko and len(set(long_ko)) < 0.7 * len(long_ko):
        errors.append("긴 본문 %d줄 중 %d줄이 서로 같은 번역이다. 줄마다 그 원문을 옮긴다(복사해 채우지 않는다)."
                      % (len(long_ko), len(long_ko) - len(set(long_ko))))
    return ("FAIL" if errors else "PASS"), errors, warnings


def main(argv):
    if argv[:1] == ["--lane"]:
        lanes = json.loads((KIT / "lanes.json").read_text("utf-8"))
        done, bad, todo = [], [], []
        for p in lanes[argv[1]]:
            st = check(p)[0]
            (done if st == "PASS" else todo if st == "MISSING" else bad).append(p)
        print(f"갈래 {argv[1]}: 통과 {len(done)} / {len(lanes[argv[1]])}, 고칠 것 {bad or '없음'}, 다음 {todo[0] if todo else '없음(끝)'}")
        return 0
    rc = 0
    for p in argv:
        st, errs, warns = check(p)
        print(f"{p}: {st}")
        for e in errs:
            print("  오류:", e)
        for w in warns:
            print("  참고:", w)
        rc |= st != "PASS"
    return rc


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
