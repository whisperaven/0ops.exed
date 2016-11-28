#!/usr/bin/env python
# -*- coding: utf-8 -*-

# show dict
def show_dict_items(prefix, data, indent_char="", indent=True):
    for item, val in data.items():
        if isinstance(val, dict):
            print("{0}{1} ->".format(prefix, item))
            if indent and indent_char:
                prefix = prefix + indent_char
            show_dict_items(prefix, val, indent_char, indent)
        else:
            print("{0}{1} -> {2}".format(prefix, item, val))
