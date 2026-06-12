from __future__ import annotations

from collections import defaultdict
from typing import DefaultDict, Dict, List, Tuple

from classifier import ClassifiedCard


GroupMap = Dict[str, List[ClassifiedCard]]



def group_cards(cards: List[ClassifiedCard]) -> Tuple[GroupMap, List[ClassifiedCard]]:
    grouped: DefaultDict[str, List[ClassifiedCard]] = defaultdict(list)
    review: List[ClassifiedCard] = []

    for card in cards:
        if card.group_key:
            grouped[card.group_key].append(card)
        else:
            review.append(card)

    return dict(grouped), review
