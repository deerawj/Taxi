from unittest import TestCase, main
from main import validate_username
from random import shuffle, choice, randint
import string

A = string.ascii_lowercase
random_token = lambda n: "".join(choice(A) for _ in range(n))

class TestUsernameValidation(TestCase):
    def test_length(self):
        # ranges exclude the topmost value
        # so 4 to 17 means 4,5,6 ... ,15,16
        valid_lengths = range(4, 16 + 1)
        for len in range(100):
            if len in valid_lengths:
                self.assertIs(validate_username(random_token(len)), True)
            else:
                self.assertIs(validate_username(random_token(len)), False)

    def test_lowercase(self):
        error_cases = ["Apple", "APPLE"]
        for case in error_cases:
            try:
                validate_username(case)
                # ^ the above function should error
                # so if the following code should not run
                self.fail("Only lower case characters allowed")
            except ValueError:
                # if the code errors, then the test passes
                pass

    # check for leading and trailing whitespace
    def test_wstripped(self):
        error_cases = [" apple", "  apple ", "apple ", "    aa", "aa    "]
        for case in error_cases:
            try:
                validate_username(case)
                # ^ the above function should error
                # so if the following code should not run
                self.fail("Leading and trailing whitespace should be stripped")
            except ValueError:
                # if the code errors, then the test passes
                pass

    # first character must be a letter
    def test_first_char(self):
        error_cases = [
            "1apple",
            "2apple",
            "3apple",
            "4apple",
            "5apple",
            "6apple",
            "7apple",
            "8apple",
            "9apple",
            "0apple",
            "_apple",
        ]
        for case in error_cases:
            self.assertIs(validate_username(case), False)

        self.assertIs(validate_username("aapple"), True)
        self.assertIs(validate_username("bapple"), True)

        # Fuzzing
        for _ in range(1000):
            case = list(choice(error_cases))
            shuffle(case) # shuffling is done in place
            case = "".join(case)
            if case[0] in string.ascii_lowercase:
                self.assertIs(validate_username(case), True)

    # No duplicate underscores
    def test_dupe_underscore(self):
        error_cases = ["__apple", "a__pple", "ap__ple", "app__le", "appl__e", "apple__"]
        error_cases += [
            i.replace("_", "_" * randint(1, 10)) for i in error_cases
        ]  # randomly add more underscores
        for case in error_cases:
            self.assertIs(validate_username(case), False)

        self.assertIs(validate_username("a_pple"), True)
        self.assertIs(validate_username("b_pple"), True)

    def test_correct(self):
        self.assertTrue(validate_username("apple"))
        self.assertTrue(validate_username("a_ple"))
        self.assertTrue(validate_username("a_p1e"))
        self.assertTrue(validate_username("a_p12"))
        self.assertTrue(validate_username("a_pl_"))
        self.assertTrue(validate_username("a_p1_"))


if __name__ == "__main__":
    main() # running the tests