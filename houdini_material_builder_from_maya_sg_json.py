import hou, json, re

match_table_file = 'f:/dev/match_table.json'

exclude_list = []

with open(match_table_file, 'r') as f:
    match_data = json.load(f)

json_file_path = 'd:/dev/mingShip_shaders.json'
matnet_path = '/obj/matnet1'

matnet = hou.node(matnet_path)
base_shadingGroup_node = hou.node(matnet_path + '/materialbuilder1')

with open(json_file_path, 'r') as f:
    datas = json.load(f)

def dictFind(d, val):
    for k in d.keys():
        if d[k] == val:
            return k
    return


def getNode(node, upstream, connect_end, connect_start, shading_group):

    vop = None
    extended_nodes = []

    # this node generator

    if 'name' in node.keys():  
        node_type = str(node['type'])
        match_field = None

        # check this node if in the match table 

        if node_type in match_data.keys() and node['name'] not in exclude_list:
            vop = shading_group.createNode(match_data[node_type]['name'])
            match_field = match_data[node_type]
            vop.setName(node['name'])

        # if node created then match the attribites

        if vop != None:
            for parm in match_field:
                if parm != 'name':
                    p = vop.parm(parm)
                    if p != None:
                        if type(node[match_field[parm]]) is not dict:
                            if parm != 'layer':
                                if parm == 'reflect':
                                    value = node['specularColor'][0]
                                    weight = node[match_field[parm]]
                                    color = hou.Color((value[0], value[1], value[2]))
                                    v = color.hsv()[2] * weight
                                    p.set(v)

                                # color space issue , colorcorrection instead

                                if parm == 'srccolorspace':
                                    value = node[match_field[parm]]
                                    if value == 'Raw':
                                        p.set('linear')
                                    else:
                                        p.set('auto')

                                else:
                                    p.set(node[match_field[parm]])

            # bump2d and ainormalmap rule

            if node_type in match_data.keys() and match_data[node_type]['name'] == 'displacetexture':
                p = vop.parm('texture')
                if node['type'] == 'bump2d':
                    v = node['bumpValue']
                    if type(v) is dict:
                        if node['bumpValue']['node']['type'] == 'file':
                            if node['bumpValue']['node']['uvTilingMode'] == 'UDIM (Mari)':
                                p.set(node['bumpValue']['node']['fileTextureName'].replace('1001', '%(UDIM)d'))
                            else:
                                p.set(node['bumpValue']['node']['fileTextureName'])

                            exclude_list.append(node['bumpValue']['node']['name'])
                    vop.parm('type').set('bump')

                if node['type'] == 'aiNormalMap':
                    v = node['input']
                    if type(v) is dict:
                        if node['input']['node']['type'] == 'file':
                            if node['input']['node']['uvTilingMode'] == 'UDIM (Mari)':
                                p.set(node['input']['node']['fileTextureName'].replace('1001', '%(UDIM)d'))
                            else:
                                p.set(node['input']['node']['fileTextureName'])
                            exclude_list.append(node['input']['node']['name'])
                    vop.parm('type').set('normal')

            elif node_type == 'file':
                if node['uvTilingMode'] == 'UDIM (Mari)':
                    tmp = vop.parm('map').eval()
                    vop.parm('map').set(tmp.replace('1001', '%(UDIM)d'))

                cc = shading_group.createNode('colorcorrection')
                cc.setNamedInput('ClrIn', vop, 'clr')
                if vop.parm('srccolorspace').eval() == 'auto':
                    cc.parm('Gamma').set(0.454)

                if upstream[connect_end]['slot'] == 'outAlpha':
                    if upstream[connect_end]['node']['alphaIsLuminance'] == 'False':
                        vop.parm('signature').set('v4')
                        extended = shading_group.createNode('hvecgetcompon')
                        extended.parm('part').set(3)
                        extended.setNamedInput('hvec', cc, 'ClrOut')
                        extended_nodes.append(extended)
                        extended_nodes.append(cc)

                    else:
                        extended = shading_group.createNode('luminance')
                        extended.setNamedInput('rgb', cc, 'ClrOut')
                        extended_nodes.append(extended)
                extended_nodes.append(cc)

            elif match_data[node_type]['name'] == 'turbnoise':
                extended = shading_group.createNode('uvcoords')
                vop.setNamedInput('pos', extended, 'uv')

            elif node_type == 'lamber':
                vop.parm('reflect').set(0)
                vop.parm('metallic').set(0)

            elif node_type == 'V Ramp':
                if upstream[connect_end]['slot'] == 'outAlpha':
                    vop.parm('ramptype').set(1)

            elif node_type == 'aiCurvature':
                vop.parm('space').set(1)

        # sub node generator

        for attr in node:
            if type(node[attr]) is dict:
                if 'node' in node[attr].keys():
                    sub, extends = getNode(node[attr]['node'], node, attr, node[attr]['slot'], shading_group)

                    # try to connect to next

                    parm_end = dictFind(match_field, attr)
                    if node[attr]['node']['type'] in match_data.keys():
                        sub_match_field = match_data[node[attr]['node']['type']]
                        sub_data = node[attr]['node']
                        parm_start = dictFind(sub_match_field, node[attr]['slot'])
                        if parm_end != None:
                            if len(extends) > 0:
                                if sub_data['type'] == 'file' and node[attr]['slot'] == 'outAlpha':
                                    if node[attr]['node']['alphaIsLuminance']  == 'False':
                                        vop.setNamedInput(parm_end, extends[0], 'fval')
                                    else:
                                        vop.setNamedInput(parm_end, extends[0], 'lum')
                                elif sub_data['type'] == 'file':
                                    vop.setNamedInput(parm_end, extends[0], 'ClrOut')
                            elif parm_start != None:
                                vop.setNamedInput(parm_end, sub, parm_start)
                            else:
                                pass
                        else:
                            pass

    return vop, extended_nodes


for data in datas:
    for sg in data:
        new_sg_node = hou.copyNodesTo([base_shadingGroup_node], matnet)[0]
        new_sg_node.move(hou.Vector2(2.0, 0.0))
        new_sg_node.setName(sg)
        for shader in data[sg]:
            layer, extends = getNode(data[sg][shader], data[sg], shader, '', new_sg_node)
            if shader == 'surfaceShader':
                layer_unpack = new_sg_node.createNode('layerunpack')
                compute_lighting = new_sg_node.createNode('computelighting')
                surface_output = new_sg_node.node('surface_output')
                surface_output.setNamedInput('F', compute_lighting, 'out_F')
                surface_output.setNamedInput('N', layer_unpack, 'N')
                surface_output.setNamedInput('Of', compute_lighting, 'out_Of')
                surface_output.setNamedInput('Cf', compute_lighting, 'Cf')
                if layer != None:
                    compute_lighting.setNamedInput('layer', layer, 'layer')
                    layer_unpack.setNamedInput('layer', layer, 'layer')
            if shader == 'displacementShader':
                if layer != None:
                    disp_output = new_sg_node.node('displacement_output')
                    disp_output.setNamedInput('P', layer, 'dispP')
                    disp_output.setNamedInput('N', layer, 'dispN')

