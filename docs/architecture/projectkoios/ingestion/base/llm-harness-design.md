# Nominal objects as rails for LLM programming

## Working hypothesis

We treat the codebase as part of the LLM harness, not merely as the product the
LLM happens to edit.

Our working hypothesis is straightforward: the easiest reliable way to impose
structure on an LLM programmer is to put that structure into ordinary
programming patterns that the model must follow. A paragraph in a prompt is a
soft instruction. A named abstract base, a concrete immutable subclass, a
constructor invariant, a request/result type, and a mirrored test are harder to
ignore accidentally because they appear in imports, type checking, inheritance,
and review diffs.

In laboratory language, the source tree is part of the apparatus. If we want a
model to distinguish an identity from a derivation, or a validation record from
an action result, we should not ask it to remember the distinction from prose
alone. We should give each concept a nominal type and make the relationship
visible in code.

This is a practical hypothesis, not a claim that inheritance automatically
produces good design. We expect the pattern to help when the base names a real
domain role and its subclasses retain meaningful state. We expect it to fail
when abstract classes are decorative, when one generic object is used as an
envelope for unrelated values, or when inheritance hides rather than clarifies
ownership.

## Origin: `struct → function → struct`

The starting pattern is familiar functional programming:

```text
immutable input struct → function → immutable output struct
```

Project Koios expresses that data flow with object-oriented syntax:

```text
DataObjectActionRequest → DataObjectActionizer → DataObjectActionResult
```

The classes are not an invitation to build a mutable object graph. They are
nominal, immutable structs with explicit constructors and invariants. The
actionizer is still function-like: it receives one complete value and returns
one complete value. In that sense, this is a functional programming discipline
implemented with object-oriented syntax.

The choice of syntax is deliberate. A protocol can say that an object has the
right methods, but it does not force the object to declare what role it plays.
A test can show that selected examples behave correctly, but it cannot prevent a
model from moving consequential behavior into an untested side path. A nominal
base makes the intended category part of the program. The model must either use
the category or visibly depart from it.

This is the main harness hypothesis: programming patterns constrain generation
more reliably than prose alone. We use inheritance here less for classic
object-oriented reuse and more as a set of rails around a functional data flow.

## Why this helps an LLM

An LLM is very good at producing locally plausible code. The harder problem is
maintaining the same architectural distinctions across many files and many
turns. Loose helper functions, structural protocols, generic dictionaries, and
large utility modules give the model many superficially valid places to put the
next behavior. That freedom increases architectural drift.

Nominal objects reduce the number of plausible answers:

- `AbstractIdentity` says that a value exists to identify retained evidence or
  processing state.
- `AbstractDerivation` says that a record was derived from retained evidence and
  must not be mistaken for source evidence or acceptance.
- `AbstractValidation` says that a record reports completed contract checking;
  it does not grant scientific or human approval.
- `DataObjectActionRequest` and `DataObjectActionResult` mark the exact input and
  output of an action.
- `DataObjectActionizer` owns the behavior that transforms the request into the
  result.

The model can still write bad code, but it has to cross an obvious boundary to
do so. That makes mistakes easier for static analysis, tests, and reviewers to
see.

## How a model escapes the rails

LLM programmers often solve the immediate test while escaping the intended
behavior boundary. Here, a behavior sandbox means the allowed route through
named inputs, owners, actions, and outputs; it is an architectural sandbox, not
a security sandbox. The output may be correct for the observed case while the
architecture quietly becomes less inspectable. Colloquially, this is where
“AI slop” hides: not necessarily in syntax errors, but in opaque places that
allow behavior without a clear owner.

Common escape routes include:

- private classes that carry important state but avoid the domain hierarchy;
- large private methods that contain several unnamed decisions;
- private helper modules that become unreviewed alternate implementations;
- generic `object`, `Any`, dictionary, tuple, `Context`, or `Payload` values that
  erase the role of their contents;
- metadata fields used as an untyped side channel for behavior;
- compatibility facades and broad re-exports that conceal actual ownership;
- local imports and `TYPE_CHECKING` blocks used to tolerate circular ownership;
- callbacks, closures, dynamic attribute access, or catch-all adapters that move
  behavior outside the nominal request/result path;
- tests that assert only output examples while ignoring identity, provenance,
  bounds, serialization, and ownership.

Private code is not automatically wrong. A short private method can clarify the
implementation of the class that genuinely owns the behavior. The smell appears
when privacy is used as opacity: a private class, method, or module becomes a
place to encode a meaningful state transition that should have been a named
record or action. The review question is not “does the name start with an
underscore?” It is “could this code change domain behavior without crossing a
visible contract?”

Generic objects deserve the same scrutiny. A generic container is convenient
because the model can put almost anything into it. That is precisely why it is a
weak harness boundary. When a value matters to identity, provenance, replay,
validation, publication, or acceptance, it should have a concrete immutable
owner.

## The vocabulary

Use the narrowest established term that describes the represented value:

| Term | Meaning |
| --- | --- |
| Identity | A stable name or provenance-bearing identity record |
| Derivation | Immutable state produced from retained evidence |
| Validation | Immutable evidence that contract checks completed |
| Request | One complete immutable input to an action |
| Result | One complete immutable output from an action |
| Actionizer | Behavior that transforms a request into a result |
| Assembly | A composite domain object built from ordered members |
| Projection | A derived view that remains traceable to its authority |
| Publication | A durable write or publication contract |

Do not use a grander process word when a direct verb is available. For example,
“link warnings” is clearer than “materialize warnings.” In table reconstruction,
`TableStructureResult.from_derivations` creates canonical warnings and links
them to the final cells and structures. The result owner says exactly where that
responsibility lives.

Likewise, prefer “processing steps” and “responsibility boundaries” over “phase
separation.” The design goal is not to invent workflow jargon. The goal is to
make it obvious which object owns which decision.

## Concrete-object rule

A base class is useful only when concrete subclasses carry a complete,
inspectable value or own a real action boundary.

Good examples include:

- a derivation containing the exact structure and warning drafts it produced;
- a validation record identifying the object and count it validated;
- a request retaining all exact upstream evidence;
- a result retaining the request, outputs, warnings, processor identity, and
  stable result identity.

Bad examples include:

- a stateless utility class containing unrelated static methods;
- a generic `Envelope`, `Context`, or `Payload` used for several domain roles;
- an abstract class added only to satisfy a naming convention;
- a class whose only purpose is to hide free functions without representing
  state or an action.

Small arithmetic or formatting operations may remain methods of the object that
owns the invariant. We do not create a class for every line of code. We create a
class when the program needs a named value, responsibility, or lifecycle.

## Review method: start with code smell

For LLM-produced changes, code-smell review is the first architectural filter.
Passing tests show that observed examples still work; they do not show that the
model put responsibilities in durable places.

Reviewers should first ask:

1. Does every concrete class have one clear owner module?
2. Does every abstract base name a real domain role?
3. Is state immutable at the contract boundary?
4. Are identities derived by the object they identify?
5. Are derivation and validation represented separately?
6. Does an action have concrete request and result classes?
7. Are warnings, provenance, and bounds retained rather than implied?
8. Did a `helpers`, `utils`, generic envelope, compatibility facade, or broad
   root export appear because the model could not choose an owner?
9. Did consequential behavior disappear into a private class, private method,
   private module, `Any`, generic `object`, dictionary, tuple, or metadata side
   channel?
10. Are local imports or `TYPE_CHECKING` blocks concealing circular ownership?
11. Are tests checking behavior and stable bytes, not only class names and
    inheritance?
12. Could the implementation change domain behavior without crossing a visible
    constructor, request/result boundary, identity, or validation record?

The common smells are useful experimental observations. A growing utility
module suggests missing ownership. A 400-line method suggests that several
represented values are still implicit. Repeated positional tuples suggest a
missing nominal record. A compatibility facade can hide that consumers have not
migrated to the actual owner. A private implementation tree can provide an
opaque second architecture beneath the documented one. A class hierarchy with
no invariant or retained state suggests ceremony rather than structure.

Code-smell review does not replace behavioral verification. After ownership is
credible, we still run linting, formatting, type checking, focused tests, full
tests, package inspection, and stable identity or serialization comparisons.
The two forms of evidence answer different questions.

## Experimental loop

We use a simple loop:

1. State the architectural hypothesis for the change.
2. Capture stable identities and serialized bytes before refactoring.
3. Encode ownership with nominal bases and concrete immutable subclasses.
4. Keep action boundaries explicit with request/result classes.
5. Add mirrored owner tests and behavioral integration tests.
6. Review independently for code smell before reviewing style details.
7. Compare identities, serialized bytes, package contents, and full tests.
8. Revise the pattern when it creates ceremony, cycles, or unclear ownership.

This makes the approach falsifiable. The nominal-object hypothesis is weakened
if it consistently produces more circular imports, more boilerplate-only tests,
more ambiguous ownership, or no reduction in review findings. It is strengthened
when independent reviewers can identify responsibilities quickly, generated
changes land in the expected owner, and behavior-preserving refactors become
easier to verify.

## Boundary of the claim

These bases improve software structure; they do not establish scientific truth.
A derivation is not an accepted interpretation. A validation record is not
scientific validation. A successful result is not publication authorization.
Those distinctions remain explicit because an LLM is otherwise likely to blur
similarly named states.

The practical rule is colloquial but useful: if a distinction matters, make the
model type it, construct it, validate it, and test it. Do not leave the most
important architecture living only in a prompt.
