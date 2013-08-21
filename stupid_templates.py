"""A stupidly simple, unsafe, and inefficient template engine."""

import re


def parse(source):
    root = nodes = []
    stack = []
    while 1:
        text, delim, source = source.partition('{%')
        nodes.append(('text', text))
        if not delim:
            return root
        code, _, source = source.partition('%}')
        code = code.strip()

        match = re.match('for\s+(\w+)\s+in\s+(.+)', code)
        if match:
            item_name, expr = match.groups()
            child_nodes = []
            nodes.append(('for', (item_name, expr, child_nodes)))
            stack.append(nodes)
            nodes = child_nodes
            continue

        match = re.match('if\s+(.+)', code)
        if match:
            expr, = match.groups()
            child_nodes = []
            nodes.append(('if', (expr, child_nodes)))
            stack.append(nodes)
            nodes = child_nodes
            continue

        assert code == 'end'
        nodes = stack.pop()


def render(nodes, context, write):
    for node_type, value in nodes:
        if node_type == 'text':
            write(value.format(**context))
        elif node_type == 'for':
            item_name, expr, child_nodes = value
            for value in eval(expr, context, context):
                inner_context = context.copy()
                inner_context[item_name] = value
                render(child_nodes, inner_context, write)
        elif node_type == 'if':
            expr, child_nodes = value
            if eval(expr, context, context):
                render(child_nodes, context, write)
        else:
            assert 0, node_type


if __name__ == '__main__':
    import sys
    render(parse('''
        {foo}
        {% for i in bar %}
            [{i}]
            {% if i == 'abc' %}{% for c in i %}{c} {% end %}
    '''), dict(foo=4, bar=[-2, 'abc', 'baz']), sys.stdout.write)
