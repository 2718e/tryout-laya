## Background

Heres an example of a saved request

```
{
    "metadata": {
        "clientId": "yt-sponsor-skip",
        "uri": "https://www.youtube.com/watch?v=OtuNKZh2gnA"
    },
    "model": "jev-latest",
    "questions": {
        "anchor_line": {
            "criteria": {
                "L071": null,
                "L072": null,
                "L073": null,
                "L074": null,
                "L075": null,
                "L076": null,
                "L077": null,
                "L078": null,
                "L079": null,
                "L080": null,
                "L081": null,
                "L082": null,
                "L083": null,
                "L084": null,
                "L085": null,
                "L086": null,
                "L087": null,
                "L088": null,
                "L089": null,
                "L090": null,
                "L091": null,
                "L092": null,
                "L093": null,
                "L094": null,
                "L095": null,
                "L096": null,
                "L097": null,
                "L098": null,
                "L099": null,
                "L100": null,
                "L101": null,
                "L102": null,
                "L103": null,
                "L104": null,
                "L105": null,
                "L106": null,
                "L107": null,
                "L108": null,
                "L109": null,
                "L110": null,
                "none": "No line in this excerpt names a sponsor, its product or its offer."
            },
            "instructions": {
                "definition": "A sponsor segment is the part of a video that exists to promote a third party that paid for placement: a product, service, app or company. It is usually read by the creator.",
                "not_a_sponsor_segment": [
                    "The creator promoting their own merchandise, membership, Patreon, newsletter, courses or other videos.",
                    "Asking viewers to like, comment, subscribe or share.",
                    "Thanking viewers, patrons or the crew.",
                    "Content that stays on the subject of the video."
                ],
                "question": "Which labelled line is the first line that names the sponsor, its product, or its offer? For example \"thanks to X for sponsoring\", \"X is an app that\", \"today's video is brought to you by X\", or a discount code or link for X. Choose the first such line, not the lead-in before it.",
                "shape": "A sponsor segment normally has three parts, and it begins with the first one: 1. a lead-in, where the creator leaves the subject of the video and starts a story, an anecdote, a problem, a question, a joke or a \"quick break\" whose only purpose is to arrive at the sponsor; 2. the pitch, where the sponsor or its product is named and described; 3. the offer, with a link, discount code, free trial, QR code or \"link in the description\". The lead-in can last several minutes and can sound like normal content until the sponsor is named. It still belongs to the sponsor segment from its first line."
            },
            "type": "choice"
        },
        "sponsor_starts_here": {
            "criteria": {
                "false": "No sponsor segment begins in this excerpt. Either it is all regular content, or a sponsor segment that started before this excerpt is still running through it.",
                "true": "Somewhere in this excerpt the creator leaves the subject of the video and starts a sponsor segment: a lead-in, a pitch or an offer for a paying third party."
            },
            "instructions": {
                "definition": "A sponsor segment is the part of a video that exists to promote a third party that paid for placement: a product, service, app or company. It is usually read by the creator.",
                "not_a_sponsor_segment": [
                    "The creator promoting their own merchandise, membership, Patreon, newsletter, courses or other videos.",
                    "Asking viewers to like, comment, subscribe or share.",
                    "Thanking viewers, patrons or the crew.",
                    "Content that stays on the subject of the video."
                ],
                "question": "Does a sponsor segment begin somewhere in this excerpt of the video transcript?",
                "shape": "A sponsor segment normally has three parts, and it begins with the first one: 1. a lead-in, where the creator leaves the subject of the video and starts a story, an anecdote, a problem, a question, a joke or a \"quick break\" whose only purpose is to arrive at the sponsor; 2. the pitch, where the sponsor or its product is named and described; 3. the offer, with a link, discount code, free trial, QR code or \"link in the description\". The lead-in can last several minutes and can sound like normal content until the sponsor is named. It still belongs to the sponsor segment from its first line."
            },
            "type": "noul"
        }
    },
    "state": {
        "excerpt_position": "part 3 of 5 of the video",
        "video_title": "Bacteria Are Forming Memories With No Brain or Neurons",
        "video_transcript_excerpt": "L071| system. And so here it seems to rely on a built-in early warning system that\nL072| gives it a kind of a memory, allowing it to prepare way ahead of time. And it\nL073| does so by using a specific sensor. On its outer boundary, there is actually a\nL074| protein referred to as PMRB. You can kind of think of it as a specialized keyhole, which in this case\nL075| seems to contain the metal nickel. And so, when the bacteria enters human body,\nL076| first the immune system throws a very tiny non-lethal amount of chemical\nL077| stressors, such as hydrogen peroxide, at these bacteria. And it's not enough to\nL078| kill the bacteria, but it basically acts like a warning shot. And when this\nL079| hydrogen peroxide hits this metal key, it basically primes this particular\nL080| protein, changing it into a slightly different shape, and serving as a kind\nL081| of button. With this particular sensor now becoming triggered, and actually\nL082| staying on for at least 90 minutes. And that basically allows this bacterium to\nL083| remember that the danger is nearby, which actually turns on its entire\nL084| shield of mechanisms and defenses, preventing it from being destroyed by\nL085| other immune cells. And so, if suddenly there is some kind of an antibiotic or\nL086| some other immune attack coming from the body itself, during these 90 minutes,\nL087| the bacteria is already prepared and has a very high chance of surviving. And\nL088| well, in practice, that's basically what happens. These bacteria tend to survive\nL089| a lot of different antibiotics, and up until this study, it was not entirely\nL090| clear how all of this worked. And here, this was confirmed when some of the\nL091| strains that did not contain this warning system, basically got wiped out\nL092| pretty much instantly. And in this case, this study is important because it\nL093| showed us that nickel seems to act as a very important survival strategy, and\nL094| specifically seems to create a survival memory. But, because we now know this,\nL095| scientists can design drugs that might specifically target or block these\nL096| nickel detectors, essentially taking away this early system, and allowing\nL097| antibiotics to kill these superbugs. So, definitely quite an intriguing discovery\nL098| of yet another unusual memory system. Which actually brings us to this next\nL099| fundamental question and this next fundamental discovery. How can various\nL100| physical traits and memories, especially, be inherited across generations if the DNA sequence does not\nL101| change itself? And well, for nearly a century, the main dogma in biology\nL102| stated that inherited physical characteristics are exclusively determined by letters in the DNA. But,\nL103| some of the recent studies, especially the ones from Northwestern University\nL104| led by Dr. Adison Mayer, proved that bacteria seem to store memories in their\nL105| gene regulatory networks, or basically those networks that turn off various\nL106| genes. And here they were able to demonstrate that if you temporarily perturb a cell by, for example, briefly\nL107| deactivating a single gene or possible changing the environment by maybe\nL108| increasing temperature or the pH levels, it then starts a major chain reaction\nL109| inside the cell. And as one of the genes changes the state, all of the\nL110| neighboring genes seem to be affected as well. And so, by the time the original"
    }
}
```

and the response

```
{
    "answers": {
        "anchor_line": {
            "action": {
                "act_probability": 1.0
            },
            "answer_confidence": 0.6462,
            "choice": "L073",
            "confidence": 0.7808,
            "probabilities": {
                "L071": 0.025,
                "L072": 0.0034,
                "L073": 0.6462,
                "L074": 0.0001,
                "L075": 0.0001,
                "L076": 0.0003,
                "L077": 0.0,
                "L078": 0.0001,
                "L079": 0.001,
                "L080": 0.0003,
                "L081": 0.0012,
                "L082": 0.0031,
                "L083": 0.0006,
                "L084": 0.0003,
                "L085": 0.0002,
                "L086": 0.0,
                "L087": 0.0,
                "L088": 0.0001,
                "L089": 0.0,
                "L090": 0.0,
                "L091": 0.0,
                "L092": 0.0,
                "L093": 0.0,
                "L094": 0.0,
                "L095": 0.0,
                "L096": 0.0,
                "L097": 0.0,
                "L098": 0.0,
                "L099": 0.0,
                "L100": 0.0,
                "L101": 0.0,
                "L102": 0.0,
                "L103": 0.0,
                "L104": 0.0,
                "L105": 0.0,
                "L106": 0.0,
                "L107": 0.0,
                "L108": 0.0,
                "L109": 0.0,
                "L110": 0.0001,
                "none": 0.3174
            },
            "type": "choice"
        },
        "sponsor_starts_here": {
            "action": {
                "act_probability": 1.0
            },
            "answer_confidence": 0.5526,
            "confidence": 0.5526,
            "noul": 0.4474,
            "type": "noul"
        }
    },
    "model": "laya-rl-agent",
    "routing": {
        "detection": {
            "diacritic_rate": 0.0,
            "is_english": true,
            "language": "en",
            "language_undecided": false,
            "non_latin_fraction": 0.0,
            "script": "latin",
            "script_profile": {
                "latin": 1.0
            }
        },
        "model": "english",
        "reason": "English Latin text",
        "repo": "convaiinnovations/laya",
        "workflow": null
    },
    "usage": {
        "input_tokens": 1024,
        "output_tokens": 0
    }
}
```

Something I noticed there - and possibly in a few other examples - is that higher numbered lines - or lines appearing later in the input - seem to be be being assigned lower probabilities.

COuld be worth checking this further

## What I want to do

analyse the data in the .logs/requests.db to figure out if there is a relation between the line number in the request - relative to the lowest line number - and the probability assigned in the output.

what I mean by "relative to the lowest line number" - in the example given in `##background` the labels are "L071","L072", "L073"... "L110" - the respective relative positions would then be 0,1,2,...39 - this could be used to combine results from different requests. For now, exclude entries in the database where there are not 40 lines (40 labels starting with L, and none.)

## What to build

Before starting, refactor to rename the `tryout_laya/` folder to `src/`, then create an `eval/` folder under `src/`, create a script (and more files or subfolders if it makes sense to split things up).

Use some statistical method to work out the correlation between relative line number and the average probability assigned to that relative line number in the response.

also report the raw values on the console alongside the statistics and make a graph.