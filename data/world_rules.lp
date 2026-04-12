% world_rules.lp -- Base Answer Set Program for Fantasy Author
%
% These integrity constraints encode the Creative Constitution's core rules
% as formal logic.  Clingo's solver proves satisfaction or reports violations.
%
% ASP syntax reminder:
%   - predicates are lowercase, Variables are Capitalized
%   - :- body.   means "it is false that body holds" (integrity constraint)
%   - #show p/n. restricts output to predicate p with arity n
%   - % begins a comment
%
% See ARCHITECTURE_PLAN.md Section 9.5.4.

% ============================================================
% Rule 1: Every institution has a public face AND a hidden agenda
% ============================================================
:- institution(I), not has_public_face(I).
:- institution(I), not has_hidden_agenda(I).

% ============================================================
% Rule 2: Conflicts require resource scarcity or info asymmetry
% ============================================================
:- conflict(C), not driven_by_scarcity(C), not driven_by_info_asymmetry(C).

% ============================================================
% Rule 3: No isolated characters -- every character pair must
%          have at least one goal conflict (directly or transitively)
% ============================================================
:- character(A), character(B), A != B,
   not exists_goal_conflict(A, B), not exists_goal_conflict(B, A).

% ============================================================
% Rule 4: No ability without cost
% ============================================================
:- ability(A, System), not has_cost(A, System).

% ============================================================
% Rule 5: Historical causality -- every event has an explicit cause
% ============================================================
:- historical_event(E), not has_explicit_cause(E).

% ============================================================
% Rule 6: Knowledge stratification -- every topic must have
%          at least 2 knowledge layers (public belief + hidden truth)
% ============================================================
:- topic(T), #count{L : knowledge_layer(T, L)} < 2.

% ============================================================
% Rule 7: No generic tropes without mechanism
% ============================================================
:- trope(T), not has_mechanism(T).

% ============================================================
% Rule 8: Timeline consistency -- no character can be at two
%          distinct locations at the same time step
% ============================================================
:- character_at(C, L1, T), character_at(C, L2, T), L1 != L2.

% ============================================================
% Rule 9: Character knowledge boundaries -- a character cannot
%          act on information they have not been exposed to
% ============================================================
:- acts_on_knowledge(C, Fact), not knows(C, Fact).

% ============================================================
% Output: show validation-relevant atoms
% ============================================================
#show institution/1.
#show character/1.
#show conflict/1.
#show ability/2.
#show historical_event/1.
#show topic/1.
#show trope/1.
