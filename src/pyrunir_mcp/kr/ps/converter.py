from __future__ import annotations

from pyrunir.datasets import LiftedTaskSearchContext
from pytyr.formalism.planning import (
    FluentFDRFact,
    FluentFunction,
    FluentFunctionBindingData,
    FluentFunctionData,
    FluentGroundAtom,
    FluentGroundAtomData,
    FluentGroundFunctionTerm,
    FluentGroundFunctionTermData,
    FluentPredicate,
    FluentPredicateBindingData,
    FluentPredicateData,
    Object,
    ObjectData,
)
from pytyr.planning.ground import State as GroundState
from pytyr.planning.lifted import State as LiftedState


class GroundToLiftedStateConverter:
    def __init__(self, search_context: LiftedTaskSearchContext) -> None:
        self._search_context = search_context
        self._repository = search_context.task.get_repository()
        self._fdr_context = search_context.task.get_fdr_context()

    def convert(self, state: GroundState) -> LiftedState:
        fluent_facts = [self._copy_fluent_fact(fact) for fact in state.fluent_facts()]
        fluent_fterm_values = [self._copy_fluent_fterm_value(value) for value in state.fluent_fterm_values()]
        return self._search_context.state_repository.create_state(
            fluent_facts,
            fluent_fterm_values,
        )

    def _copy_object(self, obj: Object) -> Object:
        return self._repository.get_or_create(ObjectData(obj.get_name()))

    def _copy_fluent_predicate(self, predicate: FluentPredicate) -> FluentPredicate:
        builder = FluentPredicateData(predicate.get_name(), predicate.get_arity())
        return self._repository.get_or_create(builder)

    def _copy_fluent_ground_atom(self, atom: FluentGroundAtom) -> FluentGroundAtom:
        predicate = self._copy_fluent_predicate(atom.get_predicate())
        objects = [self._copy_object(obj) for obj in atom.get_objects()]
        binding = self._repository.get_or_create(FluentPredicateBindingData(predicate, objects))
        return self._repository.get_or_create(FluentGroundAtomData(binding))

    def _copy_fluent_fact(self, fact: FluentFDRFact) -> FluentFDRFact:
        atom = fact.get_atom()
        if atom is None:
            raise ValueError("fluent FDR fact has no atom")
        copied_atom = self._copy_fluent_ground_atom(atom)
        return self._fdr_context.get_fact(copied_atom)

    def _copy_fluent_function(self, function: FluentFunction) -> FluentFunction:
        builder = FluentFunctionData(function.get_name(), function.get_arity())
        return self._repository.get_or_create(builder)

    def _copy_fluent_ground_function_term(self, fterm: FluentGroundFunctionTerm) -> FluentGroundFunctionTerm:
        function = self._copy_fluent_function(fterm.get_function())
        objects = [self._copy_object(obj) for obj in fterm.get_objects()]
        binding = self._repository.get_or_create(FluentFunctionBindingData(function, objects))
        return self._repository.get_or_create(FluentGroundFunctionTermData(binding))

    def _copy_fluent_fterm_value(self, value: tuple[FluentGroundFunctionTerm, float]) -> tuple[FluentGroundFunctionTerm, float]:
        fterm, number = value
        return (self._copy_fluent_ground_function_term(fterm), number)
