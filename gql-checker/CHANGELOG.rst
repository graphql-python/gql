0.8
---

* Added profile, cProfile, pstats and typing to stdlib list.
* Added new PEP8 style, that enforces grouping of importes but allows
  any ordering within the groups.

0.7
---

* Added new Smarkets style, this is equivalent to the google style
  except that any `import X` statements must come before any `from X
  import y` statments.

0.6.2
-----

* Fixed a bug where I101 messages were not suggesting the correct order in the
  default style.  The output message now outputs a message that matches the
  selected style.

0.6.1
-----

* Fixed a bug where I101 messages were not suggesting the correct order.
* Extended test harness to be able to check error messages as well as codes.
