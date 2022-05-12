import re, json, os

json_file = os.path.join(os.path.dirname(__file__), "lele.txt")
with open(
    json_file,
    "rb",
) as fh:
    bad_json = fh.read().decode(errors="replace")
    # print(bad_json)
    improved_json = re.sub(r'"\s*$', '",', bad_json[:], flags=re.MULTILINE)
    # print(improved_json)

    # good_json = re.sub(r'(?<!")(?P<word>[\w-]+)\b(?!")', '"\g<word>"',
    #   improved_json)
    # good_json = re.sub(r'(?<[\{\s])(?P<word>[\w-]+)(?=[:\s])', '"\g<word>"',
    #   improved_json)
    # good_json = re.sub(r'([\{\[\s])(?P<word>[\w-]+)([:,\]\s])', '\1"\g<word>"\3',
    #   improved_json)
    good_json = re.sub(
        r"(?<=[\{\[\s])(?P<word>[\w-]+)(?=[:,\]\s])", '"\g<word>"', improved_json
    )
    # print(good_json)

# with open('out.js', 'w') as fh:
#     fh.write(good_json)

data = json.loads(good_json)
print(data)
