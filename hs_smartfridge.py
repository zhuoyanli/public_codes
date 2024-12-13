import json
from typing import List, Dict, Optional, Any


class Item:
    def __init__(self, name: str, freshness: int, daily_spoil: int = 0):
        self._name = name
        self._freshness = freshness
        if daily_spoil < 0:
            raise RuntimeError("Daily spoil must not be negative value")
        self._daily_spoil = daily_spoil

    @property
    def name(self):
        return self._name

    @property
    def non_perishable(self) -> bool:
        return True if not self._daily_spoil else False

    @property
    def freshness(self) -> int:
        if self._daily_spoil == 0:
            return -1
        else:
            return self._freshness

    def spoil(self) -> int:
        """
        Returns -1 if the item is non_perishable
        """
        if not self._daily_spoil:
            return -1
        self._freshness = self._freshness - self._daily_spoil if self._freshness > self._daily_spoil else 0
        return self._freshness

    def as_dict(self) -> Dict[str, any]:
        _dict = dict(
            name=self._name
        )
        if self.non_perishable:
            _dict.update(
                non_perishable=True
            )
        else:
            _dict.update(
                freshness=self._freshness,
                daily_spoil=self._daily_spoil
            )
        return _dict

from enum import Enum


# assume chicken good for 3 days
# assume apple good for a week

class Freshness(Enum):
    chicken = 9
    apple = 14

class DailySpoil(Enum):
    chicken = 3
    apple = 2
    waterbottle = 0

def get_item(name: str, freshness: Optional[int] = None, daily_spoil: Optional[int] = None) -> Item:
    if freshness is None:
        if name not in Freshness.__members__:
            # just assume unknown item is non-perishable
            freshness = 1
        else:
            freshness = Freshness[name].value
    if daily_spoil is None:
        if name not in DailySpoil.__members__:
            # just assume unknown item is non-perishable
            daily_spoil = 0
        else:
            daily_spoil = DailySpoil[name].value
    return Item(name, freshness, daily_spoil)


class DailyRunnerable:
    def daily_update(self):
        raise NotImplementedError

class CronRunner:
    def run_daily(self, runnable: DailyRunnerable):
        runnable.daily_update()

    def run(self, runnable: DailyRunnerable):
        self.run_daily(runnable)

    def notify(self, message: str):
        pass

cron_runner = CronRunner()

MESSAGE_ITEM_ZERO_STOCK = "Item stock runs out: {item_name}"
MESSAGE_ITEM_SPOILED = "Item spoiled and count: {item_count} {item_name}"

class SmartFridge():
    DISPLAY_TEMPLATE_ITEM = "{item_name}, {item_count} Count"
    DISPLAY_TEMPLATE_ITEM_NONPERISH = "{item_name}, non-perishable, {item_count} Count"
    DISPLAY_TEMPLATE_ITEM_PERISHABLE = "{item_name}, freshness at {freshness}"
    DISPLAY_TEMPLATE_ITEM_TOTAL = "Total item count: {total_count}"

    def __init__(self, capacity: int, freshness_threshold: int = 2):
        self._cap = capacity
        # should use a linkedlist actually
        self._cabinet: List[Item] = []
        self._item_counter: Dict[str, int] = {}
        self._freshness_threshold = freshness_threshold

    def put(self, item_name: str, item_quantity: int):
        if item_quantity > self._cap - len(self._cabinet):
            raise RuntimeError(f"Fridge free capacity is less than: {item_quantity}")
        self._cabinet.extend([get_item(item_name)] * item_quantity)
        self._item_counter[item_name] = self._item_counter.get(item_name, 0) + item_quantity

    def exit(self, item_name: str, item_quantity: int):
        if item_name not in self._item_counter:
            raise KeyError(f"Item not found in fridge: {item_name}")
        if item_quantity > self._item_counter[item_name]:
            raise ValueError(f"Item insufficient to exit: {item_name} of count {item_quantity}")
        item_exited = 0
        idx = 0
        _new_cab: List[Item] = []
        while idx < len(self._cabinet) and item_exited < item_quantity:
            if self._cabinet[idx].name != item_name:
                _new_cab.append(self._cabinet[idx])
            else:
                item_exited += 1
            idx += 1
        if idx < len(self._cabinet) - 1:
            _new_cab.extend(self._cabinet[idx:])
        self._cabinet = _new_cab
        self._item_counter[item_name] = self._item_counter[item_name] - item_quantity
        if self._item_counter[item_name] == 0:
            cron_runner.notify(MESSAGE_ITEM_ZERO_STOCK.format(item_name=item_name))

    def daily_update(self):
        for item_name, item_count in self._item_counter.items():
            if item_count == 0:
                cron_runner.notify(MESSAGE_ITEM_ZERO_STOCK.format(item_name=item_name))
                # remove the item
                self._item_counter.pop(item_name)
        spoil_item: Dict[str, int] = {}
        for item in self._cabinet:
            if item.non_perishable:
                continue
            freshness = item.spoil()
            if freshness <= self._freshness_threshold:
                spoil_item[item.name] += spoil_item.get(item.name, 0) + 1
        for _item, _item_count in spoil_item:
            cron_runner.notify(MESSAGE_ITEM_SPOILED.format(
                item_name=_item.name,
                item_count=_item_count
            ))

    def display(self, show_freshness: bool = False, redirect: bool = False) -> Optional[str]:
        display = ""
        if not self._item_counter:
            display = "Empty fridge: No item found"
        elif not show_freshness:
            display = "Item(s) in fridge:\n"
            for item_name in sorted(self._item_counter.keys()):
                display += SmartFridge.DISPLAY_TEMPLATE_ITEM.format(
                    item_name=item_name,
                    item_count=self._item_counter[item_name]
                )
                display += "\n"
        else:
            display = "Item(s) in fridge with freshness:\n"
            for item_name in sorted(self._item_counter.keys()):
                for item in self._cabinet:
                    if item.name != item_name:
                        continue
                    if item.non_perishable:
                        # only display non-perishable once
                        display += SmartFridge.DISPLAY_TEMPLATE_ITEM_NONPERISH.format(
                            item_name=item.name,
                            item_count=self._item_counter[item.name]
                        )
                        display += "\n"
                        break
                    else:
                        display += SmartFridge.DISPLAY_TEMPLATE_ITEM_PERISHABLE.format(
                            item_name=item.name,
                            freshness=item.freshness
                        )
                        display += "\n"
        display += SmartFridge.DISPLAY_TEMPLATE_ITEM_TOTAL.format(
            total_count=len(self._cabinet)
        )
        display += "\n"
        if not redirect:
            print(display, end="")
            return
        else:
            return display

    def as_dict(self) -> Dict[str, Any]:
        if not self._item_counter:
            return {}
        json_obj = {
            item_name: []
            for item_name in self._item_counter.keys()
        }
        for item in self._cabinet:
            json_obj[item.name].append(item.as_dict())
        return json_obj

def test_fridge():
    fridge = SmartFridge(20)
    fridge.put("chicken", 4)
    disp = fridge.display(redirect=True)
    assert "chicken, 4 Count" in disp
    fridge.exit("chicken", 3)
    disp = fridge.display(redirect=True)
    assert "chicken, 1 Count" in disp
    fridge.exit("chicken", 1)
    disp = fridge.display(redirect=True)
    assert "chicken, 0 Count" in disp
    fridge.put("waterbottle", 1)
    fridge.put("chicken", 1)
    fridge.put("apple", 3)
    disp = fridge.display(redirect=False)
    disp = fridge.display(show_freshness=True)
    print(json.dumps(fridge.as_dict(), indent=2))
    disp = fridge.display(redirect=True)
    assert "chicken, 1 Count" in disp
    assert "apple, 3 Count" in disp
    assert "waterbottle, 1 Count" in disp
    fridge.put("chicken", 5)
    disp = fridge.display(redirect=True)
    assert "chicken, 6 Count" in disp
    assert "apple, 3 Count" in disp
    fridge.exit("chicken", 5)
    disp = fridge.display(redirect=True)
    assert "chicken, 1 Count" in disp
    fridge.exit("chicken", 1)
    disp = fridge.display(redirect=True)
    assert "chicken, 0 Count" in disp
    assert "apple, 3 Count" in disp
    fridge.put("apple", 4)
    disp = fridge.display(redirect=True)
    assert "apple, 7 Count" in disp

test_fridge()
