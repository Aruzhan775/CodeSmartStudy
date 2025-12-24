# webapp/seed_adaptive_en.py
from django.db import transaction
from webapp.models import AdaptiveQuestion

IDX_TO_OPT = {0: "A", 1: "B", 2: "C", 3: "D"}

DATA = {
  "python-basics": {
    "title": "Python Basics",
    "levels": {
      1: [
        ("What is the output of print(2 + 2)?", ["22", "4", "Error", "5"], 1),
        ("Which keyword starts a conditional block in Python?", ["for", "if", "while", "switch"], 1),
        ("What is the type of True in Python?", ["int", "str", "bool", "float"], 2),
        ("How do you create a variable x with value 10?", ["let x = 10", "x := 10", "int x = 10", "x = 10"], 3),
        ("What is the index of the first element in a list?", ["1", "0", "-1", "first"], 1),
        ("Which function returns the length of a list lst?", ["count(lst)", "size(lst)", "lst.len()", "len(lst)"], 3),
        ("What does == do?", ["Assigns a value", "Compares values", "Concatenates strings", "Creates a list"], 1),
        ("What is the output of print('Py' + 'thon')?", ["Py thon", "Py+thon", "Python", "Error"], 2),
        ("Which function converts a string to an integer (if possible)?", ["str()", "int()", "bool()", "list()"], 1),
        ("How do you write a single-line comment in Python?", ["// comment", "# comment", "<!-- comment -->", "/* comment */"], 1),
        ("What is the output of print(5 // 2)?", ["3", "2.5", "2", "Error"], 2),
        ("What does range(3) produce in a for-loop?", ["0, 1, 2", "1, 2, 3", "0, 1, 2, 3", "3, 2, 1"], 0),
      ],
      2: [
        ("What is the output of [x*x for x in [1,2,3]]?", ["[1, 2, 3]", "[1, 4, 9]", "[2, 4, 6]", "Error"], 1),
        ("How do you access value by key 'a' in dict d?", ["d.key('a')", "d.getkey('a')", "d['a']", "d(a)"], 2),
        ("What is the output of print('A' * 3)?", ["A3", "AAA", "A A A", "Error"], 1),
        ("Which slice gets elements with indices 1 and 2 from lst?", ["lst[1:3]", "lst[1..3]", "slice(lst,1,3)", "lst(1,3)"], 0),
        ("Which structure is immutable?", ["list", "dict", "tuple", "set"], 2),
        ("What does enumerate(lst) return?", ["Pairs (index, value)", "Sorted list", "A copy of the list", "Only indexes"], 0),
        ("What is the result of set([1,1,2])?", ["{1,1,2}", "[1,2]", "{1,2}", "Error"], 2),
        ("What is bool('')?", ["True", "False", "''", "Error"], 1),
        ("Which is a correct f-string example with variable name?", ["'Hi {name}'", "f'Hi {name}'", "format('Hi name')", "Hi + {name}"], 1),
        ("How do you unpack a = [1,2] into x and y?", ["x = a[0:2]", "unpack(a)", "x,y := a", "x, y = a"], 3),
        ("What does list.append(x) do?", ["Returns new list", "Adds x to the end", "Removes x", "Sorts the list"], 1),
        ("What is the result of 3 in [1,2,3]?", ["3", "False", "True", "Error"], 2),
      ],
      3: [
        ("Why is def f(a=[]): risky?", ["It is a syntax error", "The same list is shared between calls", "a becomes a tuple", "It always leaks memory immediately"], 1),
        ("Which is more memory-efficient for large sequences?", ["A generator", "A list", "They are always equal", "Only depends on CPU"], 0),
        ("What does with open(...) as f: guarantee?", ["File is always opened read-only", "File is automatically closed", "File becomes global", "Permissions are reset"], 1),
        ("Deep copy vs shallow copy: which statement is correct?", ["Deep copy does not copy nested objects", "Deep copy copies nested objects too", "Shallow copy copies only strings", "They are identical"], 1),
        ("What is *args in a function definition?", ["A dict of keyword arguments", "A tuple of positional arguments", "A list of keys", "A limit on parameters"], 1),
        ("What is **kwargs in a function definition?", ["A tuple of positional arguments", "A dict of keyword arguments", "Only one argument", "A list of values"], 1),
        ("What is a closure?", ["A function that remembers outer variables", "A class without methods", "A function without return", "An import statement"], 0),
        ("What does nonlocal do inside a nested function?", ["Makes variable global", "Creates a new local variable", "Refers to variable in the nearest enclosing scope", "Prevents modifications"], 2),
        ("What is the result of (lambda x: x+1)(5)?", ["5", "x+1", "6", "Error"], 2),
        ("Why do we use try/except?", ["To loop over a list", "To handle exceptions", "To create classes", "To import packages"], 1),
        ("What is an iterator?", ["Any function", "An object you can call next() on", "Only a list", "Only a string"], 1),
        ("What does if __name__ == '__main__': usually mean?", ["Checks script is run directly", "Checks the username", "Starts a server automatically", "Checks virtualenv"], 0),
      ],
    },
  },

  "logic-structures": {
    "title": "Logic and Data Structures",
    "levels": {
      1: [
        ("What is (True and False)?", ["True", "False", "1", "Error"], 1),
        ("What is (True or False)?", ["False", "Error", "True", "0"], 2),
        ("What is not True?", ["True", "0", "False", "Error"], 2),
        ("What does the > operator do?", ["Assigns", "Compares greater-than", "Divides", "Concatenates"], 1),
        ("Which structure stores elements in order by index?", ["set", "dict", "list", "graph"], 2),
        ("A stack is which rule?", ["FIFO", "LIFO", "Random", "Sorted"], 1),
        ("A queue is which rule?", ["LIFO", "FIFO", "Random", "Sorted"], 1),
        ("How do you check if x is in list a?", ["a has x", "x in a", "contains(a,x)", "a[x]"], 1),
        ("What is the goal of sorting?", ["Encrypt data", "Remove duplicates", "Order elements", "Speed up the internet"], 2),
        ("A condition is best described as:", ["Always a number", "True/False expression", "Always a string", "Always a list"], 1),
        ("Loops are used for:", ["Repeating actions", "Only addition", "Opening files", "Raising exceptions"], 0),
        ("What is len(set([1,1,2]))?", ["3", "1", "Error", "2"], 3),
      ],
      2: [
        ("What does Big-O O(n) mean?", ["Constant time", "Linear time", "Quadratic time", "Factorial time"], 1),
        ("Binary search works correctly only if:", ["Array is sorted", "Array is empty", "All numbers are unique", "You have a dict"], 0),
        ("Average lookup time in a hash table is:", ["O(n!)", "O(n^2)", "O(log n)", "O(1)"], 3),
        ("What is essential in recursion?", ["Only print statements", "A base case", "Only sorting", "Only loops"], 1),
        ("Which supports fast insertion at the front (conceptually)?", ["array/list", "linked list", "tuple", "set"], 1),
        ("DFS and BFS are traversals of:", ["graphs/trees", "strings", "files", "database tables"], 0),
        ("A stable sort means:", ["Works only for ints", "Does not reorder equal elements", "Always O(1)", "Removes duplicates"], 1),
        ("What is 5 % 2?", ["2", "0", "Error", "1"], 3),
        ("Which structure is best for unique items?", ["list", "tuple", "set", "stack"], 2),
        ("A dictionary (dict) is:", ["key → value mapping", "index → value mapping", "only values", "only keys"], 0),
        ("Amortized complexity is:", ["Always the maximum", "Average over a sequence of operations", "Always the minimum", "Only for graphs"], 1),
        ("FIFO means:", ["Last in, first out", "First in, first out", "Random order", "Sorted order"], 1),
      ],
      3: [
        ("Dynamic programming is:", ["Bubble sort", "Solving via subproblems + memoization", "Recursion without memory", "Only for graphs"], 1),
        ("Best structure to check balanced parentheses '()()'?", ["dict", "stack", "set", "random list"], 1),
        ("A min-heap property:", ["Root is minimum", "Root is maximum", "Always fully sorted", "Cannot insert"], 0),
        ("Shortest path algorithm for non-negative weights:", ["DFS", "Dijkstra", "Bubble sort", "QuickSort"], 1),
        ("Tree traversal Left-Root-Right is called:", ["pre-order", "post-order", "in-order", "level-order"], 2),
        ("Quicksort worst-case time complexity:", ["O(log n)", "O(1)", "O(n)", "O(n^2)"], 3),
        ("A hash collision means:", ["Different keys map to same index", "Sorting failed", "File not found", "Infinite loop"], 0),
        ("AVL tree balancing ensures:", ["Height stays ~log n", "Everything becomes O(1)", "Duplicates removed", "Converted to list"], 0),
        ("Topological sorting applies to:", ["Any graph", "A DAG", "Only arrays", "Only strings"], 1),
        ("Main difference BFS vs DFS:", ["BFS is depth-first, DFS is level-order", "BFS explores by levels, DFS goes deep", "They are identical", "DFS works only on trees"], 1),
        ("An adjacency list is:", ["List of neighbors for each vertex", "Matrix multiplication", "Call stack", "List of files"], 0),
        ("Search in a balanced BST is:", ["O(n!)", "O(1)", "O(n^2)", "O(log n)"], 3),
      ],
    },
  },

  "files-exceptions-functions": {
    "title": "Files, Exceptions, Functions",
    "levels": {
      1: [
        ("How do you open a file for reading?", ["open('a.txt','w')", "open('a.txt','r')", "read('a.txt')", "file('a.txt')"], 1),
        ("Which mode opens a file for writing and truncates it?", ["a", "x", "w", "r"], 2),
        ("Which mode appends to the end of a file?", ["r", "a", "w", "rb"], 1),
        ("Why do we use try/except?", ["To catch errors", "To open files", "To create classes", "To sort lists"], 0),
        ("How do you define a function in Python?", ["def f():", "function f()", "fun f()", "define f()"], 0),
        ("What does return do?", ["Prints value", "Returns a value", "Opens a file", "Imports a module"], 1),
        ("How do you close a file manually?", ["end(f)", "f.stop()", "f.close()", "close(f)"], 2),
        ("What does with open(...) as f do?", ["Auto-closes the file", "Only opens .py files", "Makes file global", "Deletes the file"], 0),
        ("What happens if you open a missing file for reading?", ["SyntaxError", "FileNotFoundError", "ZeroDivisionError", "TypeError"], 1),
        ("What is finally used for?", ["Runs only on success", "Runs only on error", "Replaces except", "Runs no matter what"], 3),
        ("How do you read the entire file as a string?", ["f.close()", "f.append()", "f.read()", "f.write()"], 2),
        ("How do you read a file line by line?", ["for line in f:", "while f:", "scan(f)", "lines(f)"], 0),
      ],
      2: [
        ("How do you catch a ValueError specifically?", ["catch ValueError:", "except:", "except ValueError:", "if ValueError:"], 2),
        ("How do you catch different exceptions?", ["You can't", "Use multiple except blocks", "Only with if", "Only with finally"], 1),
        ("What does raise do?", ["Suppresses an error", "Throws an exception", "Prints a log", "Opens a file"], 1),
        ("How do you accept any number of positional arguments?", ["*args", "**kwargs", "args*", "kw*"], 0),
        ("How do you accept any number of keyword arguments?", ["*args", "kwargs*", "**kwargs", "named*"], 2),
        ("What is a lambda?", ["A short anonymous function", "A loop", "A file", "A class"], 0),
        ("Which is the modern convenient string formatting style?", ["Only concatenation", "f-strings", "% formatting only", "format_map only"], 1),
        ("What does f.seek(0) do?", ["Closes the file", "Deletes the file", "Moves cursor to the start", "Opens again"], 2),
        ("How do you read one line from a file?", ["f.read()", "f.readline()", "f.readlines()", "f.line()"], 1),
        ("What does f.readlines() return?", ["One string", "A list of lines", "Bytes", "An error"], 1),
        ("An exception is:", ["A signal of an error/unusual situation", "A variable type", "A loop type", "A module"], 0),
        ("How do you safely get a key from dict without KeyError?", ["d['k']", "d.key('k')", "safe(d,'k')", "d.get('k')"], 3),
      ],
      3: [
        ("Exception vs BaseException: correct statement?", ["No difference", "BaseException includes system-exiting exceptions too", "Exception is wider", "BaseException is only for files"], 1),
        ("How do you re-raise a caught exception?", ["throw", "raise", "break", "return"], 1),
        ("A context manager is basically:", ["Any dict", "Any list", "Object with __enter__ / __exit__", "Any module"], 2),
        ("What does yield do in a function?", ["Makes it a generator", "Closes a file", "Speeds up CPU", "Creates a class"], 0),
        ("A decorator is:", ["A function that wraps another function", "A data type", "A file", "An exception"], 0),
        ("Scope means:", ["Algorithm speed", "Where a variable is accessible", "A loop type", "File encoding"], 1),
        ("Why does encoding matter when reading text files?", ["It never matters", "Only affects numbers", "Otherwise you may get garbled text/errors", "Only affects booleans"], 2),
        ("What does open(..., encoding='utf-8') do?", ["Encrypts file", "Reads/writes using UTF-8", "Compresses file", "Deletes BOM always"], 1),
        ("How can you print a stack trace in Python?", ["Use traceback module", "Use random module", "Use math module", "You can't"], 0),
        ("What is a custom exception?", ["Only ValueError", "A class inheriting Exception", "Only SystemExit", "Only IOError"], 1),
        ("How to guarantee resource cleanup without with?", ["try/finally", "if/else", "for/while", "lambda"], 0),
        ("A closure in functions is:", ["A function that stores outer variables", "A function without args", "A function without return", "A function only for files"], 0),
      ],
    },
  },
}

def seed_adaptive(clear_existing: bool = True) -> None:
    topic_codes = list(DATA.keys())

    if clear_existing:
        deleted, _ = AdaptiveQuestion.objects.filter(topic_code__in=topic_codes).delete()
        print(f"🧹 Deleted old adaptive questions (and related rows): {deleted}")

    created = 0
    with transaction.atomic():
        for code, meta in DATA.items():
            for level, questions in meta["levels"].items():
                for q_text, options, correct_i in questions:
                    if len(options) != 4:
                        raise ValueError(f"Question must have exactly 4 options: {q_text}")
                    if correct_i not in (0, 1, 2, 3):
                        raise ValueError(f"correct_i must be 0..3: {q_text}")

                    AdaptiveQuestion.objects.create(
                        topic_code=code,
                        level=int(level),
                        text=q_text,
                        option_a=options[0],
                        option_b=options[1],
                        option_c=options[2],
                        option_d=options[3],
                        correct_option=IDX_TO_OPT[correct_i],
                        is_active=True,
                    )
                    created += 1

    print(f"✅ Seed done! Added questions: {created}")

if __name__ == "__main__":
    seed_adaptive(clear_existing=True)